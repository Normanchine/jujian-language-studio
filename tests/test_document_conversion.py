"""Conversion input bounds and cancellation of an owned helper process."""
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from document_conversion import page_range, read_markdown, local_convert, ConversionCancelled


class ConversionTests(unittest.TestCase):
    def test_native_pdf_key_recovery_requires_an_explicit_key_heading(self):
        from helpers.mineru_convert import source_key_sections
        self.assertEqual([], source_key_sections('1. B\n2. D\nOrdinary text'))
        self.assertEqual(['Answer Key\n1. B\n2. D'], source_key_sections('Passage text\nAnswer Key\n1. B\n2. D\nOther text'))
        self.assertEqual([], source_key_sections('Answer Key\n1. Birds fly south.'))

    def test_page_range_is_inclusive_and_invalid_ranges_fail(self):
        self.assertEqual((None, None), page_range(''))
        self.assertEqual((0, 0), page_range('1'))
        self.assertEqual((2, 11), page_range('3-12'))
        for value in ('0', '9-2', '1,2', '-1', '3--5'):
            with self.assertRaises(ValueError):
                page_range(value)

    def test_text_encoding_and_binary_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'source.md'
            path.write_text('日本語の文章', encoding='utf-16')
            self.assertEqual('日本語の文章', read_markdown(path))
            path.write_bytes(b'a\x00b')
            with self.assertRaises(ValueError):
                read_markdown(path)

    def test_cancel_terminates_owned_conversion_and_preserves_input(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'helpers').mkdir()
            helper = root / 'helpers/mineru_convert.py'
            helper.write_text('''import argparse, pathlib, time
p=argparse.ArgumentParser();p.add_argument('--output');args,other=p.parse_known_args()
pathlib.Path(args.output,'started').write_text('ready')
time.sleep(30)
''', encoding='utf-8')
            source = root / 'fixture.pdf'
            source.write_bytes(b'owned cancellation fixture')
            output = root / 'output'
            cancel = threading.Event()
            errors = []
            def run():
                try:
                    local_convert(source, output, sys.executable, 'en', '', cancel, lambda message: None)
                except Exception as exc:
                    errors.append(exc)
            with patch('document_conversion.ASSETS', root):
                worker = threading.Thread(target=run)
                worker.start()
                deadline = time.monotonic() + 5
                while not (output / 'started').exists() and worker.is_alive() and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertTrue((output / 'started').exists())
                cancel.set()
                worker.join(6)
                self.assertFalse(worker.is_alive())
            self.assertTrue(errors and isinstance(errors[0], ConversionCancelled), errors)
            self.assertEqual(b'owned cancellation fixture', source.read_bytes())


if __name__ == '__main__':
    unittest.main()
