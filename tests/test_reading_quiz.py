"""Reading-paper parsing and AI answer validation."""
import unittest

from reading_quiz import ai_answer_prompt, apply_ai_answers, parse_reading_papers

TOEFL = """## Passage 1\u3000Dinosaur Feathers

Paleontologists once thought dinosaurs were covered in scales. Fossils found in China show traces of feathers around skeletons. The feathers were probably used for insulation rather than flight.

### Passage 1 Questions

**1.** The word "traces" is closest in meaning to

- A. development
- B. signs
- C. copies
- D. shadows

**2.** What did the fossils suggest?

- A. All dinosaurs could fly.
- B. Feathers were more common than once thought.
- C. Dinosaurs lived in Europe.
- D. Feathers were used as tools.

## Passage 2\u3000Urban Trees

Urban trees cool the air when water evaporates from their leaves. Young trees still need soil and water.

1. How do trees cool the air?
A. By blocking wind
B. By evaporating water
C. By growing taller
D. By producing shade only

Answer Key
1. B
2. C
"""


class ReadingQuizTests(unittest.TestCase):
    def test_document_end_key_binds_unique_numbers_across_passages(self):
        from multipaper_fixture import raw_text
        papers = parse_reading_papers(raw_text(), 'en')['papers']
        self.assertEqual([2, 3, 1], [len(p['questions']) for p in papers])
        self.assertEqual([['B', 'D'], ['A', 'C', 'B'], ['D']],
                         [[q['answer'] for q in p['questions']] for p in papers])

    def test_repeated_numbers_keep_their_own_passage_keys(self):
        text = '''Passage 1 Library

The library opens on Monday.

1. When does it open?
A. Monday
B. Friday

Answer Key
1. A

Passage 2 Market

The market opens on Friday.

1. When does it open?
A. Monday
B. Friday

Answer Key
1. B
'''
        papers = parse_reading_papers(text, 'en')['papers']
        self.assertEqual(['A', 'B'], [p['questions'][0]['answer'] for p in papers])

    def test_multiple_passages_and_answer_table(self):
        result = parse_reading_papers(TOEFL, "en")
        self.assertEqual(2, len(result["papers"]))
        first, second = result["papers"]
        self.assertEqual("Dinosaur Feathers", first["title"])
        self.assertEqual(2, len(first["questions"]))
        self.assertEqual(1, len(second["questions"]))
        self.assertEqual("B", second["questions"][0]["answer"])
        self.assertIn("Urban trees cool the air", second["body"])
        self.assertNotIn("Answer Key", second["body"])

    def test_japanese_options_and_answer_line(self):
        text = """第1問　次の文章を読んで、後の問いに答えなさい。

日本の町では人口が減っている。若い人が都市へ移る地域もある。

問1　本文の内容と合っているものはどれか。
ア　すべての町で人口が増えている。
イ　若い人が都市へ移る町がある。
ウ　地方の仕事が増えている。
エ　学校はどこにでもある。

問2　最近の動きはどれか。
ア　小さな会社が遠くの客と仕事をする。
イ　都市の人口が急に減っている。
ウ　地方の学校が増えている。
エ　若い人が地方へ移るのをやめた。

答え：1 イ　2 ア
"""
        result = parse_reading_papers(text, "ja")
        questions = result["papers"][0]["questions"]
        self.assertEqual(["B", "A"], [question["answer"] for question in questions])
        self.assertEqual(4, len(questions[0]["options"]))
        self.assertNotIn("第1問", result["papers"][0]["body"])

    def test_bold_option_does_not_claim_to_be_an_answer(self):
        text = """Reading 1  A Short History of Tea

Tea was first drunk in China and later reached Europe.

1. Where was tea first drunk?
- A. Britain
- **B. China**
- C. Japan
- D. India
"""
        question = parse_reading_papers(text, "en")["papers"][0]["questions"][0]
        self.assertEqual("", question["answer"])
        self.assertEqual("", question["answer_source"])

    def test_text_without_questions_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_reading_papers("Just a plain article with no questions.", "en")

    def test_missing_option_does_not_shift_answer_letters(self):
        text = 'Passage 1 Garden\n\nThe garden opens on Sunday.\n\n1. When?\nA. Monday\nC. Sunday\nD. Friday\nAnswer: C'
        with self.assertRaises(ValueError):
            parse_reading_papers(text, 'en')

    def test_conflicting_keys_are_not_silently_overwritten(self):
        text = 'Passage 1 Garden\n\nThe garden opens on Sunday.\n\n1. When?\nA. Monday\nB. Sunday\n\nAnswer Key\n1. A\n1. B'
        result = parse_reading_papers(text, 'en')
        self.assertEqual('', result['papers'][0]['questions'][0]['answer'])
        self.assertTrue(result['warnings'])

    def test_duplicate_question_numbers_require_new_passage_boundary(self):
        text = 'Passage 1 Garden\n\nThe garden opens on Sunday.\n\n1. When?\nA. Monday\nB. Sunday\n\n1. What?\nA. Trees\nB. Water'
        with self.assertRaises(ValueError):
            parse_reading_papers(text, 'en')

    def test_multi_select_is_not_graded_as_single_choice(self):
        text = 'Passage 1 Garden\n\nThe garden opens on Sunday.\n\n1. Select two answers.\nA. Monday\nB. Sunday\nC. Friday\nD. Tuesday'
        with self.assertRaises(ValueError):
            parse_reading_papers(text, 'en')

    def test_empty_ai_answer_is_not_converted_to_A(self):
        questions = [{'number': '1', 'stem': 'Q', 'options': ['a', 'b'], 'answer': ''}]
        count = apply_ai_answers({'answers': [{'number': '1', 'answer': '', 'explanation': 'unknown', 'quote': 'An exact source sentence.'}]}, questions, 'An exact source sentence.')
        self.assertEqual(0, count)
        self.assertEqual('', questions[0]['answer'])

    def test_checkmark_and_explanation_do_not_leak_into_options(self):
        text = 'Passage 1 Garden\n\nThe garden opens on Sunday.\n\n1. When?\nA. Monday\nB. Sunday ✓\n解析：The answer is B because it opens on Sunday.'
        question = parse_reading_papers(text, 'en')['papers'][0]['questions'][0]
        self.assertEqual(['Monday', 'Sunday'], question['options'])
        self.assertEqual('', question['answer'])
        self.assertIn('because', question['explanation'])

    def test_markdown_answer_table_with_blank_rows_preserves_source_keys(self):
        questions = '\n\n'.join(f'{n}. When does the garden open?\nA. Monday\nB. Sunday' for n in range(1, 21))
        keys = '\n\n'.join(f'| {n} | B |' for n in range(1, 21))
        text = 'Passage 1 Garden\n\nThe garden opens every Sunday.\n\n' + questions + '\n\nAnswer Key\n\n| Question | Answer |\n| --- | --- |\n' + keys
        paper = parse_reading_papers(text, 'en')['papers'][0]
        self.assertEqual(20, len(paper['questions']))
        self.assertTrue(all(q['answer'] == 'B' for q in paper['questions']))
        self.assertTrue(all(q['options'] == ['Monday', 'Sunday'] for q in paper['questions']))

    def test_incomplete_question_is_skipped_with_warning(self):
        text = """Reading 1  Insertion

The passage has four marked locations.

1. What is the main idea?
A. One
B. Two
C. Three
D. Four

2. Where does the sentence best fit? Select a location.
"""
        result = parse_reading_papers(text, "en")
        self.assertEqual(1, len(result["papers"][0]["questions"]))
        self.assertTrue(result["warnings"])

    def test_ai_answers_are_validated_and_located(self):
        questions = [
            {"number": 1, "stem": "Q1", "options": ["a", "b", "c", "d"], "answer": "", "explanation": ""},
            {"number": 2, "stem": "Q2", "options": ["a", "b", "c", "d"], "answer": "", "explanation": ""},
        ]
        body = "First paragraph has evidence here.\n\nSecond paragraph."
        payload = {"answers": [
            {"number": 1, "answer": "b", "explanation": "解析一", "quote": "evidence here"},
            {"number": 2, "answer": "Z", "explanation": "invalid"},
        ]}
        applied = apply_ai_answers(payload, questions, body)
        self.assertEqual(1, applied)
        self.assertEqual("B", questions[0]["answer"])
        self.assertEqual("ai", questions[0]["answer_source"])
        self.assertEqual([{"paragraph": 1, "quote": "evidence here"}], questions[0]["evidence"])
        self.assertEqual("", questions[1]["answer"])

    def test_ai_prompt_quotes_source_rules(self):
        prompt = ai_answer_prompt("Body.", [{"number": 1, "stem": "Q", "options": ["a", "b"]}], "ja")
        self.assertIn("日语", prompt)
        self.assertIn('"answer"', prompt)
        self.assertIn("原文", prompt)


if __name__ == "__main__":
    unittest.main()
