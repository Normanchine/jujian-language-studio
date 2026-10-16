"""Separate process for local Whisper transcription."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import av
import numpy as np


def merge_english_pauses(segments: list[dict]) -> list[dict]:
    """Join likely continuation fragments while retaining their original word timings."""
    merged: list[dict] = []
    for original in segments:
        segment = {**original, "words": list(original.get("words", []))}
        if merged:
            previous = merged[-1]
            gap = segment["start"] - previous["end"]
            continuation = bool(re.match(r"^[a-z(\[]", segment["text"].lstrip()))
            short_fragment = len(segment["text"].split()) <= 2
            if (not re.search(r"[.!?][\"')\]]?$", previous["text"].rstrip())
                    and 0 <= gap <= 2.5
                    and segment["end"] - previous["start"] <= 14
                    and len(previous["text"]) + len(segment["text"]) <= 180
                    and (continuation or short_fragment)):
                previous["text"] = (previous["text"].rstrip() + " " + segment["text"].lstrip()).strip()
                previous["end"] = segment["end"]
                previous["words"].extend(segment["words"])
                previous.setdefault("source_segments", 1)
                previous["source_segments"] += 1
                continue
        merged.append(segment)
    return merged


def read_audio(path: Path) -> np.ndarray:
    chunks: list[np.ndarray] = []
    with av.open(str(path)) as container:
        audio_streams = container.streams.audio
        if not audio_streams:
            raise ValueError("媒体文件没有音轨")
        resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
        for frame in container.decode(audio_streams[0]):
            for converted in resampler.resample(frame):
                chunks.append(converted.to_ndarray().reshape(-1))
        for converted in resampler.resample(None):
            chunks.append(converted.to_ndarray().reshape(-1))
    if not chunks:
        raise ValueError("音轨为空")
    return np.concatenate(chunks).astype(np.float32) / 32768.0


def main(args: list[str] | None = None) -> int:
    args = sys.argv[1:] if args is None else args
    if len(args) != 4 or args[3] not in {"auto", "ja", "en"}:
        print("usage: transcribe_job.py MEDIA OUTPUT MODEL_DIR LANGUAGE(auto|ja|en)", file=sys.stderr)
        return 2
    media, output, model_root = map(Path, args[:3])
    language = args[3]
    import torch
    import whisper

    audio = read_audio(media)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = whisper.load_model("small", device=device, download_root=str(model_root))
    result = model.transcribe(audio, language=None if language == "auto" else language,
                              task="transcribe", word_timestamps=True, fp16=device == "cuda", verbose=False)
    detected_language = result.get("language", language)
    segments = []
    for segment in result["segments"]:
        text = segment["text"].strip()
        if not text:
            continue
        words = [
            {"start": round(float(word["start"]), 3), "end": round(float(word["end"]), 3), "text": word["word"]}
            for word in segment.get("words", [])
        ]
        start = min([float(segment["start"]), *(word["start"] for word in words)])
        end = max([float(segment["end"]), *(word["end"] for word in words)])
        segments.append({
            "start": round(start, 3), "end": round(end, 3), "text": text,
            "translation": "", "reviewed": False, "words": words,
        })
    raw_segments = segments
    if detected_language == "en":
        segments = merge_english_pauses(segments)
        from subtitle_split import split_segments
        segments, _ = split_segments(segments, "en", use_model=False)
    output.write_text(json.dumps({
        "source": media.name, "model": "small", "device": device, "language": detected_language,
        "review_status": "machine_generated_unchecked", "segments": segments,
        "raw_segments": raw_segments,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"segments={len(segments)} device={device} language={detected_language}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
