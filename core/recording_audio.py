"""Local PCM recording processing. Only the outer silence is trimmed."""
from __future__ import annotations

import math
import os
from pathlib import Path
import struct
import wave


def repair_pcm_header(path: Path) -> None:
    """Recover our own canonical 44-byte PCM WAV after an interrupted write."""
    with path.open('r+b') as stream:
        header = stream.read(44)
        if (len(header) != 44 or header[:4] != b'RIFF' or header[8:16] != b'WAVEfmt '
                or header[36:40] != b'data' or struct.unpack_from('<H', header, 20)[0] != 1):
            raise ValueError('录音文件格式无法恢复；原文件已保留')
        block = struct.unpack_from('<H', header, 32)[0]
        if not block:
            raise ValueError('录音文件缺少声道信息')
        size = max(0, path.stat().st_size - 44)
        size -= size % block
        if size > 0xFFFFFFFF - 36:
            raise ValueError('录音超过 WAV 大小上限')
        stream.seek(4)
        stream.write(struct.pack('<I', size + 36))
        stream.seek(40)
        stream.write(struct.pack('<I', size))
        stream.flush()


def analyze_pcm(path: Path, padding: float = .5, threshold_db: float = -50) -> dict:
    import numpy as np
    if padding not in (.5, 1.0) or threshold_db not in (-60, -50, -40):
        raise ValueError('静音处理设置无效')
    # Bound memory by aggregating 20 ms blocks, even for long lectures.
    with wave.open(str(path), 'rb') as audio:
        rate, channels, count = audio.getframerate(), audio.getnchannels(), audio.getnframes()
        if audio.getsampwidth() != 2 or not rate or not count:
            raise ValueError('没有录到有效音频，请检查播放设备后重录')
        step = max(1, round(rate * .02))
        rms, peaks = [], []
        while data := audio.readframes(step):
            samples = np.frombuffer(data, dtype='<i2').reshape(-1, channels).astype(np.float32)
            rms.append(float(np.sqrt(np.mean(samples * samples, axis=0)).max()))
            peaks.append(float(np.abs(samples).max()) / 32768)
    loudest = max(rms, default=0)
    # Quiet playback must remain recordable; a nonzero floor rejects digital noise.
    threshold = max(3.0, min(32768 * 10 ** (threshold_db / 20), loudest * .03))
    active = [index for index, value in enumerate(rms) if value >= threshold]
    if not active or sum(rms[i] >= threshold for i in active) * step / rate < .06:
        raise ValueError('未检测到有效声音，录音已暂存。请确认播放设备或重新录制')
    first, last = active[0] * step / rate, min(count, (active[-1] + 1) * step) / rate
    duration = count / rate
    begin, end = max(0.0, first - padding), min(duration, last + padding)
    stride = max(1, math.ceil(len(peaks) / 400))
    waveform = [round(max(peaks[i:i + stride]), 4) for i in range(0, len(peaks), stride)]
    return dict(duration=duration, start=round(begin, 3), end=round(end, 3),
                soundStart=round(first, 3), soundEnd=round(last, 3), peaks=waveform,
                rate=rate, channels=channels, padding=padding, thresholdDb=threshold_db)


def export_pcm(source: Path, target: Path, start: float, end: float) -> dict:
    if not all(math.isfinite(n) for n in (start, end)) or start < 0 or end <= start:
        raise ValueError('裁剪范围无效')
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.part.wav')
    try:
        with wave.open(str(source), 'rb') as audio:
            rate = audio.getframerate()
            duration = audio.getnframes() / rate
            if end > duration + .002:
                raise ValueError('裁剪终点超过录音长度')
            begin = round(start * rate)
            remaining = min(round(end * rate), audio.getnframes()) - begin
            if remaining <= 0:
                raise ValueError('裁剪后音频为空')
            audio.setpos(begin)
            with wave.open(str(temporary), 'wb') as output:
                output.setparams(audio.getparams())
                while remaining:
                    chunk = audio.readframes(min(remaining, rate))
                    if not chunk:
                        raise ValueError('录音文件不完整，原文件已保留')
                    output.writeframes(chunk)
                    remaining -= len(chunk) // (audio.getnchannels() * audio.getsampwidth())
        with temporary.open('r+b') as stream:
            os.fsync(stream.fileno())
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    with wave.open(str(target), 'rb') as output:
        return dict(duration=output.getnframes() / output.getframerate(), path=str(target))
