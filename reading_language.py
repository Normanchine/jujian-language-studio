"""Local reading aids. Learning bands are editorial references, not JLPT claims.

Rules locate candidates only: the contextual analyser decides their actual use.
Unlisted expressions may receive a separately labelled AI estimate during analysis.
"""
from __future__ import annotations

import re

BANDS = ('basic', 'intermediate', 'advanced', 'unknown')
BAND_LABELS = {'basic': 'N5–N4', 'intermediate': 'N3–N2', 'advanced': 'N1', 'unknown': '待分级'}
REFERENCE_VERSION = 1

# pattern, reference band, textbook connection (the matched source stays intact).
GRAMMAR_REFERENCE = [
    (r'だけでなく', 'intermediate', '普通形／名词 ＋ だけでなく'),
    (r'(?:られ|れ)(?:ました|ます|た|る|ない)', 'basic', '动词被动形／可能形（须结合本句判断）'),
    (r'てから', 'basic', '动词て形 ＋ から'),
    (r'ないで', 'basic', '动词ない形 ＋ で'),
    (r'ずに', 'intermediate', '动词ない形去掉ない ＋ ずに（する→せずに）'),
    (r'があり(?:ます|ました)', 'basic', '名词 ＋ がある'),
    (r'たところ', 'intermediate', '动词た形 ＋ ところ'),
    (r'しか', 'basic', '名词など ＋ しか ＋ 否定'),
    (r'について', 'basic', '名词 ＋ について'),
    (r'にとって', 'intermediate', '名词 ＋ にとって'),
    (r'によって', 'intermediate', '名词 ＋ によって'),
    (r'に関して', 'intermediate', '名词 ＋ に関して'),
    (r'に対して', 'intermediate', '名词 ＋ に対して'),
    (r'に比べて', 'intermediate', '名词 ＋ に比べて'),
    (r'という', 'intermediate', '名词／普通形 ＋ という'),
    (r'として', 'intermediate', '名词 ＋ として'),
    (r'ことができ(?:る|ます|た|ない|ません)?', 'basic', '动词辞书形 ＋ ことができる'),
    (r'なければなら(?:ない|なかった|ぬ)', 'basic', '动词ない形去掉ない ＋ なければならない'),
    (r'なくてはいけ(?:ない|ません)', 'basic', '动词ない形去掉ない ＋ なくてはいけない'),
    (r'なくてもいい', 'basic', '动词ない形去掉ない ＋ なくてもいい'),
    (r'(?:て|で)もいい', 'basic', '动词て形 ＋ もいい'),
    (r'(?:て|で)はいけ(?:ない|ません)', 'basic', '动词て形 ＋ はいけない'),
    (r'ようにな(?:る|ります|った|りました)', 'intermediate', '动词辞书形／ない形 ＋ ようになる'),
    (r'ようにし(?:ている|ています|た|ます|よう)', 'intermediate', '动词辞书形／ない形 ＋ ようにする'),
    (r'ようにする', 'intermediate', '动词辞书形／ない形 ＋ ようにする'),
    (r'ように', 'intermediate', '动词辞书形／ない形 ＋ ように（须结合语境）'),
    (r'ようだ', 'intermediate', '普通形 ＋ ようだ（名词＋の／な形容词＋な）'),
    (r'ような', 'intermediate', '普通形 ＋ ような（后接名词）'),
    (r'ながら', 'basic', '动词ます形去掉ます ＋ ながら（同时进行用法）'),
    (r'ために', 'intermediate', '动词辞书形／名词＋の ＋ ために'),
    (r'そうです', 'basic', '普通形＋そうです／词干＋そうです（区分传闻与样态）'),
    (r'そうだ', 'basic', '普通形＋そうだ／词干＋そうだ（区分传闻与样态）'),
    (r'みたい', 'intermediate', '普通形／名词 ＋ みたい'),
    (r'らしい', 'intermediate', '普通形 ＋ らしい'),
    (r'つもり', 'basic', '动词辞书形／ない形 ＋ つもり'),
    (r'ばかり', 'intermediate', '名词／动词た形など ＋ ばかり（须结合语境）'),
    (r'(?:て|で)(?:い(?:ます|ません|る|た|ない)|お(?:きます|いた|く)|しま(?:います|った|う)|くれ(?:ました|ます|る|た)|もら(?:いました|います|う|った)|あげ(?:ました|ます|る|た)|み(?:ました|ます|る|た))', 'basic', '动词て形 ＋ 补助动词（いる／おく／しまう等）'),
    (r'(?:では|じゃ)(?:ありません(?:が)?|ない)', 'basic', '名词／な形容词 ＋ ではない／ではありません'),
    (r'ませんでした', 'basic', '动词ます形去掉ます ＋ ませんでした'),
    (r'ませんか', 'basic', '动词ます形去掉ます ＋ ませんか'),
    (r'(?:ましょ|でしょ)(?:う|うか)', 'basic', '动词ます形去掉ます ＋ ましょう／普通形 ＋ でしょう'),
    (r'にな(?:ると|ったら|ります|るため|るまで|る)', 'basic', '名词／な形容词 ＋ に ＋ なる'),
    (r'なったら', 'basic', 'なる的た形 ＋ ら'),
    (r'ところに', 'intermediate', '动词た形など ＋ ところに（须结合语境）'),
    (r'ところだ', 'intermediate', '动词辞书形／ている形／た形 ＋ ところだ'),
    (r'ことも', 'unknown', '动词普通形 ＋ こと ＋ も'),
    (r'ことは', 'unknown', '动词普通形 ＋ こと ＋ は'),
    (r'ことを', 'unknown', '动词普通形 ＋ こと ＋ を'),
    (r'ことに(?:する|した|します)', 'basic', '动词辞书形／ない形 ＋ ことにする'),
    (r'ことにな(?:る|った|ります)', 'basic', '动词辞书形／ない形 ＋ ことになる'),
    (r'ことがあ(?:る|った|ります|りません)', 'basic', '动词た形／辞书形 ＋ ことがある（区分经历与偶发）'),
    (r'たびに', 'intermediate', '动词辞书形／名词＋の ＋ たびに'),
    (r'おかげで', 'intermediate', '普通形／名词＋の ＋ おかげで'),
    (r'せいで', 'intermediate', '普通形／名词＋の ＋ せいで'),
    (r'うちに', 'intermediate', '普通形／名词＋の ＋ うちに'),
    (r'まま', 'intermediate', '动词た形／ない形／名词＋の ＋ まま'),
    (r'のに', 'basic', '普通形 ＋ のに（名词／な形容词＋な）'),
    (r'ので', 'basic', '普通形 ＋ ので（名词／な形容词＋な）'),
    (r'はず(?:だ|です|がない)', 'intermediate', '普通形 ＋ はず（名词＋の／な形容词＋な）'),
    (r'べき(?:だ|です|ではない)?', 'intermediate', '动词辞书形 ＋ べき（する可用すべき）'),
    (r'わけでは(?:ない|ありません)', 'intermediate', '普通形 ＋ わけではない'),
    (r'わけがない', 'intermediate', '普通形 ＋ わけがない'),
    (r'わけにはいかない', 'intermediate', '动词辞书形 ＋ わけにはいかない'),
    (r'わけだ', 'intermediate', '普通形 ＋ わけだ'),
    (r'に違いない', 'intermediate', '普通形／名词 ＋ に違いない'),
    (r'かもしれ(?:ない|ません)', 'basic', '普通形／名词 ＋ かもしれない'),
    (r'かどうか', 'intermediate', '普通形 ＋ かどうか'),
    (r'にしては', 'intermediate', '普通形／名词 ＋ にしては'),
    (r'にしても', 'intermediate', '普通形／名词 ＋ にしても'),
    (r'としても', 'intermediate', '普通形 ＋ としても'),
    (r'に加えて', 'intermediate', '名词 ＋ に加えて'),
    (r'に応じて', 'intermediate', '名词 ＋ に応じて'),
    (r'に沿って', 'intermediate', '名词 ＋ に沿って'),
    (r'に従って', 'intermediate', '动词辞书形／名词 ＋ に従って'),
    (r'につれて', 'intermediate', '动词辞书形／名词 ＋ につれて'),
    (r'とともに', 'intermediate', '动词辞书形／名词 ＋ とともに'),
    (r'にわたって', 'intermediate', '名词 ＋ にわたって'),
    (r'を通じて', 'intermediate', '名词 ＋ を通じて'),
    (r'を通して', 'intermediate', '名词 ＋ を通して'),
    (r'に限らず', 'intermediate', '名词 ＋ に限らず'),
    (r'に限って', 'intermediate', '名词 ＋ に限って'),
    (r'に限り', 'intermediate', '名词 ＋ に限り'),
    (r'にもかかわらず', 'intermediate', '普通形／名词 ＋ にもかかわらず'),
    (r'どころか', 'intermediate', '普通形／名词 ＋ どころか'),
    (r'ばかりか', 'intermediate', '普通形／名词 ＋ ばかりか'),
    (r'ばかりでなく', 'intermediate', '普通形／名词 ＋ ばかりでなく'),
    (r'ものの', 'intermediate', '普通形 ＋ ものの（な形容词＋な）'),
    (r'ものなら', 'intermediate', '动词可能形など ＋ ものなら'),
    (r'ことから', 'intermediate', '普通形 ＋ ことから'),
    (r'ことなく', 'intermediate', '动词辞书形 ＋ ことなく'),
    (r'ずにはいられない', 'intermediate', '动词ない形去掉ない ＋ ずにはいられない（する→せず）'),
    (r'ざるを得ない', 'intermediate', '动词ない形去掉ない ＋ ざるを得ない（する→せざる）'),
    (r'ずにはおかない', 'advanced', '动词ない形去掉ない ＋ ずにはおかない'),
    (r'にほかならない', 'advanced', '名词 ＋ にほかならない'),
    (r'にすぎない', 'intermediate', '普通形／名词 ＋ にすぎない'),
    (r'にほかならぬ', 'advanced', '名词 ＋ にほかならぬ'),
    (r'を余儀なくされ(?:る|た|ます)', 'advanced', '名词 ＋ を余儀なくされる'),
    (r'を禁じ得ない', 'advanced', '感情名词 ＋ を禁じ得ない'),
    (r'に堪えない', 'advanced', '动词辞书形／名词 ＋ に堪えない'),
    (r'をものともせず', 'advanced', '名词 ＋ をものともせず'),
    (r'いかん(?:にかかわらず|によって|では|だ)', 'advanced', '名词（＋の） ＋ いかん'),
    (r'を皮切りに', 'advanced', '名词 ＋ を皮切りに'),
    (r'に至って', 'advanced', '动词辞书形／名词 ＋ に至って'),
    (r'までもない', 'advanced', '动词辞书形 ＋ までもない'),
    (r'といったところだ', 'advanced', '名词など ＋ といったところだ'),
    (r'と相まって', 'advanced', '名词 ＋ と相まって'),
]

# Kana-only words get a reference band only when explicitly reviewed here.
KANA_BANDS = {}
for _band, _words in (
    ('basic', 'ここ そこ あそこ どこ こちら そちら あちら どちら これ それ あれ どれ そば よく いつ いつも とても たいへん たくさん すこし ちょっと もっと もう まだ また すぐ いっしょ どう どうして なぜ だれ どなた みんな ぜんぶ はじめて たぶん きっと ぜひ ゆっくり だんだん まっすぐ ほとんど ずっと さっき しばらく はっきり ちゃんと いっぱい やっと いろいろ もし しかし そして それから だから けれども じゃあ'),
    ('intermediate', 'きっかけ つい ついに つねに ますます かなり ずいぶん いよいよ それぞれ さまざま せっかく せめて むしろ まさか あえて いわゆる およそ おそらく たとえ たとえば たまたま たちまち たっぷり ぴったり すっかり さっぱり しっかり なんとか なるべく なかなか わざわざ わりと あらかじめ あくまで つまり ところが ところで なお ただし さらに しかも そのうえ したがって'),
    ('advanced', 'あながち ことごとく ひたすら もっぱら おのずと かろうじて いたって すこぶる いかにも しいて ひいては とりわけ やむをえず'),
):
    KANA_BANDS.update(dict.fromkeys(_words.split(), _band))


def reference_for(surface):
    matches = [(pattern, band, connection) for pattern, band, connection in GRAMMAR_REFERENCE
               if re.fullmatch(pattern, surface)]
    if not matches:
        band = 'basic' if surface in {'と', 'ば', 'なら', 'たら', 'ても', 'でも', 'から', 'のに', 'ので', 'のは', 'けれども'} else 'unknown'
        return {'band': band, 'connection': '', 'level_source': '内置学习分级（参考）' if band != 'unknown' else ''}
    _, band, connection = matches[0]
    return {'band': band, 'connection': connection, 'level_source': '内置学习分级（参考）' if band != 'unknown' else ''}


def ruby_segments(surface, reading):
    """Align kana anchors; return only kanji runs. Never guess a failed alignment."""
    if not reading or not re.search(r'[\u3400-\u9fff々〆ヶ]', surface): return []
    pieces = list(re.finditer(r'[\u3400-\u9fff々〆ヶ]+|[^\u3400-\u9fff々〆ヶ]+', surface))

    def align(index, position):
        if index == len(pieces): return [] if position == len(reading) else None
        piece = pieces[index]; value = piece.group()
        if not re.search(r'[\u3400-\u9fff々〆ヶ]', value):
            if not reading.startswith(value, position): return None
            return align(index + 1, position + len(value))
        ends = [len(reading)] if index == len(pieces)-1 else range(position+1, len(reading)+1)
        for end in ends:
            if end <= position: continue
            rest = align(index+1, end)
            if rest is not None:
                return [dict(start=piece.start(), end=piece.end(), reading=reading[position:end])] + rest
        return None
    return align(0, 0) or []


def query_kind(selected, language):
    value = selected.strip()
    if re.search(r'[。！？!?\n]|\.(?:\s|$)', value): return 'sentence'
    if language == 'en':
        words=value.split()
        return 'sentence' if len(words)>=7 or (len(words)>=2 and re.match(r'^(I|you|he|she|it|we|they|there)\b',value,re.I)) else 'word'
    if len(value)>=4:
        from linguistics import display_tokens
        tokens=display_tokens(value,[],'ja')
        if (tokens and tokens[-1]['category'] in {'verb','adjective','auxiliary'}
                and any(t['category']=='particle' and t['text'] in {'は','が','を'} for t in tokens)):
            return 'sentence'
    return 'sentence' if len(value) >= 22 else 'word'
