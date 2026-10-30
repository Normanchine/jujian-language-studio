"""Distinct, self-authored passages: collisions are detectable without an AI judge."""
PAPERS = [
    {'title': 'A night library',
     'body': 'The town library stays open until ten on Thursdays. Students asked for the extra hours because many of them work during the day. The library added a quiet study room on the second floor.',
     'questions': [
         {'number': 1, 'stem': 'When does the library close on Thursdays?', 'options': ['At six', 'At ten', 'At noon', 'At eight'], 'answer': 'B'},
         {'number': 2, 'stem': 'Where is the quiet study room?', 'options': ['In the basement', 'Outside the library', 'On the first floor', 'On the second floor'], 'answer': 'D'}]},
    {'title': 'A river cleanup',
     'body': 'A volunteer group cleans the riverbank on the first Saturday of each month. Members collect plastic bottles and record the number they find. They send their records to the local school so pupils can study changes over time.',
     'questions': [
         {'number': 3, 'stem': 'When does the group clean the riverbank?', 'options': ['On the first Saturday', 'Every Monday', 'On the last Sunday', 'Every afternoon'], 'answer': 'A'},
         {'number': 4, 'stem': 'What do volunteers count?', 'options': ['Boats', 'Trees', 'Plastic bottles', 'Fish'], 'answer': 'C'},
         {'number': 5, 'stem': 'Who receives the records?', 'options': ['A hotel', 'The local school', 'A railway company', 'A supermarket'], 'answer': 'B'}]},
    {'title': 'Buses on market day',
     'body': 'The village market opens on Wednesdays. On market days, the first bus leaves at seven instead of eight. The earlier departure helps sellers set up their stalls before customers arrive.',
     'questions': [
         {'number': 6, 'stem': 'Why does the first bus leave earlier?', 'options': ['To avoid rain', 'To carry school pupils', 'To save fuel', 'To help sellers prepare their stalls'], 'answer': 'D'}]}
]


def paragraphs(paper, index):
    result = [f'Passage {index+1}  {paper["title"]}', paper['body']]
    for q in paper['questions']:
        result.append(f'{q["number"]}. {q["stem"]}')
        result.extend(f'{chr(65+i)}. {option}' for i, option in enumerate(q['options']))
    return result


def raw_text():
    text = '\n\n'.join('\n\n'.join(paragraphs(p, i)) for i, p in enumerate(PAPERS))
    return text + '\n\nAnswer Key\n' + '\n'.join(f'{q["number"]}. {q["answer"]}' for p in PAPERS for q in p['questions'])
