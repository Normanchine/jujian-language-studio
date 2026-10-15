"""Minimal local Ollama JSON routing check."""

import writing
from ai_client import ask_json
from writing import WritingJob

def trace(prompt, task, limit):
    result = ask_json(prompt, task, limit)
    print("raw:", result, flush=True)
    return result

writing.ask_json = trace

draft = {"language": "en", "title": "test", "topic": "A useful habit",
         "text": "I choose myy boy. He go to school every day.", "targets": []}
job = WritingJob("review", draft)
job.resultReady.connect(lambda kind, data: print("result:", kind, data, flush=True))
job.failed.connect(lambda detail: print("error:", detail, flush=True))
job.run()
materials = WritingJob("materials", draft, "托福风格")
materials.resultReady.connect(lambda kind, data: print("materials:", kind, len(data.get("items", [])), flush=True))
materials.failed.connect(lambda detail: print("materials-error:", detail, flush=True))
materials.run()
