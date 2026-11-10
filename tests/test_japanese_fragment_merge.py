import copy
import unittest

from transcribe_job import merge_japanese_fragments


def segment(text, start, end):
    return {"text": text, "start": start, "end": end,
            "words": [{"text": text, "start": start, "end": end}]}


class JapaneseFragmentMergeTests(unittest.TestCase):
    def test_request_and_short_reply_stay_separate(self):
        source = [segment("引っ越しを手伝ってくれない", 0, 4), segment("いいけど", 4.1, 4.7),
                  segment("また引っ越すんだね", 4.75, 7)]
        self.assertEqual(merge_japanese_fragments(source), source)

    def test_three_grammatical_fragments_still_join(self):
        source = [segment("友達", 0, .45), segment("に", .5, .7), segment("会いました", .75, 1.6)]
        before = copy.deepcopy(source)
        output = merge_japanese_fragments(source)
        self.assertEqual([s["text"] for s in output], ["友達に会いました"])
        self.assertEqual(output[0]["words"], [s["words"][0] for s in source])
        self.assertEqual(source, before)

    def test_complete_sentence_is_not_a_merge_target(self):
        source = [segment("帰りました", 0, 3), segment("友達", 3.1, 3.7)]
        self.assertEqual(merge_japanese_fragments(source), source)

    def test_short_answer_keeps_its_own_card(self):
        for reply in ("はい", "うん", "いいえ", "そうですね", "ありがとう"):
            source = [segment(reply, 0, .5), segment("友達に会いました", .55, 3)]
            self.assertEqual(merge_japanese_fragments(source), source)

    def test_pause_and_long_combined_duration_block_merge(self):
        for start, end in ((.9, 2), (.55, 9)):
            source = [segment("友達に", 0, .5), segment("会いました", start, end)]
            self.assertEqual(merge_japanese_fragments(source), source)

    def test_auxiliary_continuation_still_joins(self):
        source = [segment("手伝って", 0, .7), segment("くれない", .72, 1.5)]
        self.assertEqual(merge_japanese_fragments(source)[0]["text"], "手伝ってくれない")


if __name__ == "__main__":
    unittest.main()
