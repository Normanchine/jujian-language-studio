"""Routing, dedicated-group isolation, TUN preservation, and retry decisions."""
import copy
import unittest
from unittest.mock import patch

import clash_service as clash
import download_service as downloads


class YouTubeRoutingTests(unittest.TestCase):
    def test_accept_single_video_links_only(self):
        for url in ("https://www.youtube.com/watch?v=BaW_jenozKc&list=abc",
                    "https://youtu.be/BaW_jenozKc?t=1", "https://m.youtube.com/shorts/BaW_jenozKc",
                    "https://youtube.com/live/BaW_jenozKc"):
            self.assertTrue(downloads.is_youtube_url(url), url)
            self.assertTrue(downloads.allowed_url(url))
        for url in ("http://youtu.be/BaW_jenozKc", "https://youtube.com/playlist?list=abc",
                    "https://youtube.com.evil.com/watch?v=BaW_jenozKc",
                    "https://user:pass@youtube.com/watch?v=BaW_jenozKc",
                    "https://youtube.com:99/watch?v=BaW_jenozKc", "https://youtube.com/watch?v=no"):
            self.assertFalse(downloads.allowed_url(url), url)

    def test_proxy_and_runtime_only_used_for_youtube(self):
        import yt_dlp
        for url, expected in (("https://www.bilibili.com/video/BVtest", ""),
                              ("https://youtu.be/BaW_jenozKc", "http://127.0.0.1:7897")):
            options = []

            class Client:
                def __init__(self, opts): options.append(opts)
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def extract_info(self, url, download): return {"title": "test", "formats": []}

            job = downloads.DownloadJob(url, "inspect", settings={"youtube_proxy": "http://127.0.0.1:7897"})
            errors = []
            job.failed.connect(errors.append)
            with patch.object(yt_dlp, "YoutubeDL", Client), patch.object(downloads, "deno_path", return_value="deno.exe"), \
                 patch.object(clash.ClashClient, "route_ready", return_value=False):
                job.run()
            self.assertEqual(errors, [])
            self.assertEqual(options[0]["proxy"], expected)
            self.assertEqual("js_runtimes" in options[0], bool(expected))

    def test_error_classification_does_not_rotate_on_auth_or_video_restrictions(self):
        for text in ("Sign in to confirm you're not a bot", "Private video", "HTTP Error 403", "HTTP Error 429", "Video not available"):
            self.assertFalse(downloads.is_connection_error(text))
        for text in ("Connection refused", "Connection timed out", "ProxyError", "Connection reset"):
            self.assertTrue(downloads.is_connection_error(text))

    def test_retry_rotates_only_dedicated_group_and_stops_at_three_attempts(self):
        import yt_dlp
        calls = []

        class Client:
            def __init__(self, opts): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def extract_info(self, *args, **kwargs):
                calls.append(1)
                raise RuntimeError("Connection timed out")

        job = downloads.DownloadJob("https://youtu.be/BaW_jenozKc", "inspect")
        from unittest.mock import Mock
        job._controller = Mock()
        job._candidates = ["A", "B", "C"]
        with patch.object(yt_dlp, "YoutubeDL", Client), self.assertRaisesRegex(RuntimeError, "timed out"):
            job._extract({}, job.url, False)
        self.assertEqual(len(calls), 3)
        self.assertEqual([c.args[0] for c in job._controller.select.call_args_list], ["A", "B"])

    def test_cancel_does_not_rotate(self):
        job = downloads.DownloadJob("https://youtu.be/BaW_jenozKc", "inspect")
        job.cancel_requested = True
        with self.assertRaisesRegex(RuntimeError, "取消"):
            job._extract({}, job.url, False)

    def test_auth_failure_never_switches_node(self):
        import yt_dlp
        from unittest.mock import Mock
        job = downloads.DownloadJob("https://youtu.be/BaW_jenozKc", "inspect")
        job._controller = Mock()
        job._candidates = ["A"]
        client = Mock()
        client.__enter__ = Mock(return_value=client)
        client.__exit__ = Mock(return_value=False)
        client.extract_info.side_effect = RuntimeError("Sign in to confirm you're not a bot")
        with patch.object(yt_dlp, "YoutubeDL", return_value=client), self.assertRaisesRegex(RuntimeError, "Sign in"):
            job._extract({}, job.url, False)
        job._controller.select.assert_not_called()

    def test_subscription_status_entries_are_not_nodes(self):
        self.assertFalse(clash.usable_node("剩余流量：10 GB", {"type": "Shadowsocks"}))
        self.assertFalse(clash.usable_node("套餐到期 2027", {"type": "Shadowsocks"}))
        self.assertTrue(clash.usable_node("日本 01", {"type": "Shadowsocks"}))

    def test_control_endpoint_restricted_to_loopback(self):
        for url in ("http://127.0.0.1:9097", "http://localhost:9090", "http://[::1]:9090"):
            self.assertEqual(clash.validate_loopback(url), url)
        for url in ("http://example.com:9090", "http://127.0.0.1:9090/api", "http://a:b@127.0.0.1:9090", "socks5://127.0.0.1:7897"):
            with self.assertRaises(ValueError): clash.validate_loopback(url)


class DedicatedRouteTests(unittest.TestCase):
    def client(self):
        config = {"external-controller": "127.0.0.1:9097", "mixed-port": 7897, "mode": "rule",
                  "tun": {"enable": True, "stack": "gvisor", "auto-route": True},
                  "proxies": [{"name": "A", "type": "ss"}],
                  "proxy-groups": [{"name": "shared", "type": "select", "proxies": ["A"]}]}
        with patch.object(clash, "local_profile", return_value=(None, config)):
            return clash.ClashClient({})

    def test_setup_preserves_tun_and_shared_groups_and_adds_bound_listener(self):
        import yaml
        client = self.client()
        before = {"mixed-port": 7897, "mode": "rule", "tun": copy.deepcopy(client.profile["tun"])}
        requests = []
        proxies = {"A": {"type": "Shadowsocks"}, "shared": {"type": "Selector", "all": ["A"], "now": "A"}}

        def request(path, data=None, method="GET", timeout=8):
            requests.append((path, data, method))
            if path == "/configs": return copy.deepcopy(before)
            if path == "/proxies": return {"proxies": copy.deepcopy(proxies)}
            return {}

        with patch.object(client, "request", side_effect=request), \
             patch.object(client, "route_ready", return_value=True), \
             patch.object(clash.socket, "create_connection", side_effect=ConnectionRefusedError):
            client.install_route()
        writes = [r for r in requests if r[2] != "GET"]
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0][0], "/configs?force=true")
        payload = yaml.safe_load(writes[0][1]["payload"])
        self.assertEqual(payload["tun"], before["tun"])
        self.assertEqual(payload["proxy-groups"][0], client.profile["proxy-groups"][0])
        self.assertEqual(payload["listeners"][0]["proxy"], clash.GROUP)
        self.assertEqual(payload["listeners"][0]["listen"], "127.0.0.1")
        self.assertEqual(payload["listeners"][0]["port"], clash.PORT)
        self.assertNotIn("listeners", client.profile)

    def test_stale_tun_state_blocks_reload(self):
        client = self.client()
        before = {"tun": {"enable": False}, "mode": "rule", "mixed-port": 7897}
        from unittest.mock import Mock
        client.request = Mock(return_value=before)
        with patch.object(client, "proxies", return_value={}), \
             patch.object(clash.socket, "create_connection", side_effect=ConnectionRefusedError), \
             self.assertRaisesRegex(ValueError, "TUN"):
            client.install_route()
        self.assertTrue(all(c.args[0] == "/configs" for c in client.request.call_args_list))

    def test_select_only_own_group_and_real_nodes(self):
        client = self.client()
        proxies = {clash.GROUP: {"type": "Selector", "all": ["A", "DIRECT", "shared"]},
                   "A": {"type": "Shadowsocks"}, "DIRECT": {"type": "Direct"}, "shared": {"type": "Selector"}}
        with patch.object(client, "proxies", return_value=proxies), \
             patch.object(client, "route_ready", return_value=True), patch.object(client, "request") as request:
            client.select("A")
            self.assertEqual(request.call_args.args, ("/proxies/" + clash.GROUP, {"name": "A"}, "PUT"))
            with self.assertRaises(ValueError): client.select("DIRECT")
            with self.assertRaises(ValueError): client.select("shared")


if __name__ == "__main__":
    unittest.main()
