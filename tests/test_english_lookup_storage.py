"""The English word-note store uses JSON lists across lookup and removal."""
import json
import tempfile
import unittest
from pathlib import Path

from english_vocabulary import EnglishVocabularyBridge, word_id


class EnglishLookupStorageTests(unittest.TestCase):
    def test_lookup_survives_reopen_and_can_be_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            identity = lambda: {'model': 'test'}
            paragraph = 'billion years of geologic history'
            bridge = EnglishVocabularyBridge(directory, None, identity)
            bridge.open('article', [paragraph])
            for term, meaning in [('billion', '十亿'), ('years', '年')]:
                start = paragraph.index(term)
                bridge.record_lookup(dict(paragraph=0, start=start, end=start + len(term),
                                          text=term, meaning=meaning))
            saved_path = bridge._manual_path()
            self.assertEqual(2, len(json.loads(saved_path.read_text(encoding='utf-8'))))
            reopened = EnglishVocabularyBridge(directory, None, identity)
            reopened.open('article', [paragraph])
            self.assertEqual(2, reopened.view['count'])
            self.assertTrue(reopened.removeLookup(word_id(0, 0, 7)))
            self.assertEqual(1, len(json.loads(saved_path.read_text(encoding='utf-8'))))
            final = EnglishVocabularyBridge(directory, None, identity)
            final.open('article', [paragraph])
            self.assertEqual(['years'], [row['text'] for row in final.view['paragraphs'][0]])


if __name__ == '__main__':
    unittest.main()
