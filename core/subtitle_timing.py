"""Conservative repair of numbered prompts repeated with collapsed ASR timing."""
from __future__ import annotations

import copy
import re

_DIGITS = r'[0-9０-９一二三四五六七八九十]+'
_NUMBER = re.compile(r'^\s*(' + _DIGITS + r'番|' + _DIGITS + r'(?=\s))\s*')


def repair_collapsed_repetitions(segments, language='ja'):
    """Keep spoken question numbers; retain every original in a repair audit.

    A repeated text alone is never enough: require aligned source words, a
    recent matching prompt, and at least 80% collapsed timing in its body.
    Reviewed/manual subtitles are always protected.
    """
    if language != 'ja' or not isinstance(segments, list):
        return segments, []
    output, repairs = [], []
    compact = lambda text: ''.join(text.split())
    for index, original in enumerate(segments):
        output.append(original)
        if not isinstance(original, dict):
            continue  # Let the normal subtitle validator report malformed input.
        text = original.get('text', '')
        words = original.get('words', [])
        analysis = original.get('analysis', {})
        if (not isinstance(text, str) or not isinstance(words, list) or not words
                or original.get('reviewed') or not isinstance(analysis, dict) or analysis.get('model') == 'manual'):
            continue
        match = _NUMBER.match(text)
        if not match:
            continue
        prefix, body = compact(match[1]), compact(text[match.end():])
        if len(body) < 8:
            continue
        try:
            if compact(''.join(w['text'] for w in words)) != compact(text):
                continue
            previous_match = any(
                0 <= original['start'] - previous['end'] <= 180
                and (previous_number := _NUMBER.match(previous.get('text', '')))
                and compact(previous['text'][previous_number.end():]) == body
                for previous in segments[max(0, index - 40):index] if isinstance(previous, dict))
            if not previous_match:
                continue
            number_words, body_words, offset = [], [], 0
            for word in words:
                size = len(compact(word['text']))
                if offset < len(prefix) < offset + size:
                    break  # A word crossing the boundary cannot be safely cut.
                (number_words if offset < len(prefix) else body_words).append(word)
                offset += size
            else:
                collapsed = sum(len(compact(w['text'])) for w in body_words if w['end'] - w['start'] <= .001)
                if (number_words and body_words and collapsed / len(body) >= .8
                        and body_words[-1]['end'] - body_words[0]['start'] <= .3
                        and number_words[-1]['end'] > original['start']):
                    fixed = {**original, 'text': prefix, 'end': number_words[-1]['end'],
                             'words': copy.deepcopy(number_words), 'translation': '', 'analysis': {}}
                    fixed.pop('tokens', None)
                    # Old projects already have valid number annotations. Reuse
                    # that prefix so repairing a tail need not load a dictionary.
                    tokens, token_text = [], ''
                    for token in original.get('tokens', []):
                        if not isinstance(token, dict) or not isinstance(token.get('text'), str):
                            break
                        tokens.append(token)
                        token_text += compact(token['text'])
                        if token_text == prefix:
                            fixed['tokens'] = copy.deepcopy(tokens)
                            break
                        if not prefix.startswith(token_text):
                            break
                    output[-1] = fixed
                    repairs.append({'index': index, 'reason': 'repeated-numbered-prompt-collapsed-timing-v1',
                                    'original': copy.deepcopy(original), 'text': prefix})
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            continue
    return output, repairs
