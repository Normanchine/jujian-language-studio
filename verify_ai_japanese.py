"""One real local Japanese writing guidance request."""

from writing import WritingJob

job = WritingJob("review", {"language": "ja", "topic": "勉強習慣",
                             "text": "私は毎日勉強します。昨日も勉強します。", "targets": []})
result = []
job.resultReady.connect(lambda kind, data: result.append(data))
job.failed.connect(lambda detail: print("error:", detail, flush=True))
job.run()
if not result or result[0]["language"] != "ja" or not result[0]["overall"]:
    raise SystemExit(2)
print("japanese guidance:", len(result[0]["overall"]),
      "suggestions:", len(result[0]["advice"]), flush=True)
