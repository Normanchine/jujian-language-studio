"""Exercise outer-only trimming, quiet audio, crash recovery and folder integrity."""
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import wave

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.recording_audio import analyze_pcm, export_pcm, repair_pcm_header
from core.library_folders import create_folder, read_folders
from core.recording_preferences import read_preferences, save_preferences


def write_audio(path, quiet=False):
    rate = 16000
    # Two utterances separated by a long natural pause.
    tone = (np.sin(np.arange(rate) * 2 * np.pi * 440 / rate) * (30 if quiet else 5000)).astype('<i2')
    data = np.concatenate([np.zeros(rate * 2, dtype='<i2'), tone,
                           np.zeros(rate * 3, dtype='<i2'), tone, np.zeros(rate * 2, dtype='<i2')])
    with wave.open(str(path), 'wb') as audio:
        audio.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
        audio.writeframes(data.tobytes())


class RecordingAudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.raw = self.root / 'raw.wav'
        write_audio(self.raw)

    def tearDown(self): self.temp.cleanup()

    def test_outer_trim_preserves_interior_pause_and_original(self):
        original = self.raw.read_bytes()
        result = analyze_pcm(self.raw, .5)
        self.assertAlmostEqual(result['start'], 1.5, places=2)
        self.assertAlmostEqual(result['end'], 7.5, places=2)
        target = self.root / 'out.wav'
        exported = export_pcm(self.raw, target, result['start'], result['end'])
        self.assertAlmostEqual(exported['duration'], 6, places=2)
        with wave.open(str(target), 'rb') as audio:
            audio.setpos(int(1.5 * audio.getframerate()))
            self.assertEqual(set(audio.readframes(audio.getframerate() * 3)), {0})
        self.assertEqual(self.raw.read_bytes(), original)

    def test_one_second_padding_and_quiet_playback(self):
        write_audio(self.raw, quiet=True)
        result = analyze_pcm(self.raw, 1)
        self.assertEqual((result['start'], result['end']), (1, 8))

    def test_full_silence_rejected_without_removing_raw(self):
        with wave.open(str(self.raw), 'wb') as audio:
            audio.setparams((2, 2, 48000, 0, 'NONE', 'not compressed'))
            audio.writeframes(b'\0' * 48000 * 4)
        with self.assertRaisesRegex(ValueError, '有效声音'):
            analyze_pcm(self.raw)
        self.assertTrue(self.raw.exists())

    def test_stereo_audio_in_one_channel_is_not_trimmed_away(self):
        data = np.zeros((16000 * 3, 2), dtype='<i2')
        data[16000:32000, 1] = (np.sin(np.arange(16000) * .2) * 4000).astype('<i2')
        with wave.open(str(self.raw), 'wb') as audio:
            audio.setparams((2, 2, 16000, 0, 'NONE', 'not compressed'))
            audio.writeframes(data.tobytes())
        result = analyze_pcm(self.raw)
        self.assertEqual((result['start'], result['end']), (.5, 2.5))

    def test_stale_header_recovers_all_flushed_packets(self):
        data = self.raw.read_bytes()
        with self.raw.open('r+b') as stream:
            stream.seek(4); stream.write(struct.pack('<I', 36))
            stream.seek(40); stream.write(struct.pack('<I', 0))
        repair_pcm_header(self.raw)
        self.assertEqual(self.raw.read_bytes(), data)

    def test_invalid_ranges_never_replace_existing_output(self):
        target = self.root / 'out.wav'
        target.write_bytes(b'previous')
        for start, end in ((-1, 2), (4, 3), (float('nan'), 3), (0, 99)):
            with self.assertRaises(ValueError): export_pcm(self.raw, target, start, end)
            self.assertEqual(target.read_bytes(), b'previous')

    def test_folders_persist_deduplicate_and_fail_closed(self):
        registry = self.root / 'folders.json'
        key = create_folder(registry, 'en', '学术听力')
        self.assertEqual(create_folder(registry, 'en', ' 学术听力 '), key)
        japanese = create_folder(registry, 'ja', '学术听力')
        self.assertNotEqual(key, japanese)
        self.assertEqual(len(read_folders(registry)), 2)
        registry.write_text('{broken', encoding='utf-8')
        with self.assertRaises(ValueError): create_folder(registry, 'en', '日常对话')
        self.assertEqual(registry.read_text(encoding='utf-8'), '{broken')

    def test_recording_defaults_survive_restart_and_future_versions_are_preserved(self):
        path = self.root / 'recording-settings.json'
        self.assertEqual(read_preferences(path)['deviceName'], '')
        save_preferences(path, deviceName='Headphones [Loopback]', padding=1,
                         thresholdDb=-60, transcribe=False, language='ja')
        reloaded = read_preferences(path)
        self.assertEqual((reloaded['deviceName'], reloaded['padding'], reloaded['transcribe'], reloaded['language']),
                         ('Headphones [Loopback]', 1, False, 'ja'))
        path.write_text('{"schema_version":999}',encoding='utf-8')
        with self.assertRaises(ValueError): save_preferences(path, padding=.5)
        self.assertEqual(path.read_text(encoding='utf-8'), '{"schema_version":999}')


if __name__ == '__main__': unittest.main()
