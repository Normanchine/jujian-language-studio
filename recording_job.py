"""Isolated WASAPI worker; no GUI, microphone capture or cloud requests."""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import sys
import threading
import time
import wave


def emit(kind, **values):
    print(json.dumps(dict(event=kind, **values), ensure_ascii=False), flush=True)


def loopback_devices(manager):
    default = manager.get_default_wasapi_loopback()
    result = []
    devices = list(manager.get_device_info_generator())
    for info in manager.get_loopback_device_info_generator():
        outputs = [d for d in devices if d['hostApi'] == info['hostApi'] and d['maxOutputChannels'] > 0
                   and info['name'] == d['name'] + ' [Loopback]']
        if not outputs:
            continue
        result.append(dict(index=info['index'], name=info['name'],
                           label=info['name'].removesuffix(' [Loopback]'),
                           rate=int(info['defaultSampleRate']), channels=int(info['maxInputChannels']),
                           outputIndex=outputs[0]['index'], default=info['index'] == default['index']))
    return sorted(result, key=lambda d: not d['default'])


def capture(request):
    import numpy as np
    import pyaudiowpatch as pa
    stop = threading.Event()
    failure = threading.Event()
    packets = queue.Queue(maxsize=200)

    def commands():
        # EOF also stops the child if the parent has exited.
        sys.stdin.readline()
        stop.set()

    threading.Thread(target=commands, daemon=True).start()
    path = Path(request['path'])
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = 0
    last_level = 0.0
    overflow = False
    with pa.PyAudio() as manager:
        devices = loopback_devices(manager)
        device = next((d for d in devices if d['name'] == request['device']['name']), None)
        if not device:
            raise ValueError('播放设备已断开或改变，请刷新设备后重试')
        rate, channels = device['rate'], device['channels']
        size = max(256, round(rate * .02))

        def receive(data, count, timing, status):
            nonlocal overflow
            if status:
                overflow = True
            try:
                packets.put_nowait(data)
            except queue.Full:
                failure.set()
                return None, pa.paAbort
            return None, pa.paContinue

        def silence(data, count, timing, status):
            return b'\0' * count * channels * 2, pa.paContinue

        with wave.open(str(path), 'wb') as audio:
            audio.setnchannels(channels)
            audio.setsampwidth(2)
            audio.setframerate(rate)
            audio.writeframes(b'')  # A recoverable header exists even before sound starts.
            with manager.open(format=pa.paInt16, channels=channels, rate=rate, input=True,
                              input_device_index=device['index'], frames_per_buffer=size,
                              stream_callback=receive) as stream:
                # Keep the render clock running through silent sections. Without this,
                # some WASAPI drivers deliver no loopback packets while nothing plays.
                with manager.open(format=pa.paInt16, channels=channels, rate=rate, output=True,
                                  output_device_index=device['outputIndex'], frames_per_buffer=size,
                                  stream_callback=silence):
                    emit('started', device=device)
                    received = checkpoint = time.monotonic()
                    while not stop.is_set():
                        if failure.is_set() or overflow:
                            raise OSError('录音发生音频缓冲丢失，已保留录音，请关闭高负载任务后重试')
                        try:
                            data = packets.get(timeout=.1)
                        except queue.Empty:
                            if time.monotonic() - received > 5:
                                raise OSError('播放设备未返回音频，可能已断开；已有录音已保留')
                            continue
                        audio.writeframes(data)  # Patches the header after each packet.
                        frames += len(data) // (channels * 2)
                        received = time.monotonic()
                        if received - last_level >= .12:
                            samples = np.frombuffer(data, dtype='<i2').astype(np.float32)
                            level = float(np.abs(samples).max()) / 32768 if samples.size else 0
                            emit('level', level=round(level, 4), seconds=frames / rate)
                            last_level = received
                        if received - checkpoint > 2:
                            audio._file.flush()
                            os.fsync(audio._file.fileno())
                            checkpoint = received
                        if frames * channels * 2 >= 0xF0000000:
                            raise OSError('本次录音已达到 WAV 大小上限，已有录音已保留')
                    stream.stop_stream()
                    while not packets.empty():
                        audio.writeframes(packets.get_nowait())
    emit('captured', path=str(path))


def main(args=None):
    # PyInstaller's windowed executable (and pythonw) may replace stdio with
    # None even though QProcess supplied valid redirected Windows handles.
    if sys.platform == 'win32':
        import ctypes
        import msvcrt
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetStdHandle.argtypes = [ctypes.c_uint32]
        kernel.GetStdHandle.restype = ctypes.c_void_p
        for name, number, flag, mode in (('stdout', -11, os.O_WRONLY, 'w'),
                                          ('stderr', -12, os.O_WRONLY, 'w'),
                                          ('stdin', -10, os.O_RDONLY, 'r')):
            if getattr(sys, name) is None:
                handle = kernel.GetStdHandle(number & 0xFFFFFFFF)
                if handle and handle != ctypes.c_void_p(-1).value:
                    descriptor = msvcrt.open_osfhandle(handle, flag | os.O_BINARY)
                    setattr(sys, name, os.fdopen(descriptor, mode, encoding='utf-8', buffering=1))
    sys.stdout.reconfigure(encoding='utf-8')
    args = sys.argv[1:] if args is None else args
    try:
        request = json.loads(Path(args[0]).read_text(encoding='utf-8'))
        mode = request['mode']
        if mode == 'devices':
            import pyaudiowpatch as pa
            with pa.PyAudio() as manager:
                emit('devices', items=loopback_devices(manager))
        elif mode == 'capture':
            capture(request)
        elif mode == 'analyze':
            from core.recording_audio import analyze_pcm, repair_pcm_header
            source = Path(request['path'])
            repair_pcm_header(source)
            emit('analyzed', **analyze_pcm(source, request['padding'], request['thresholdDb']))
        elif mode == 'export':
            from core.recording_audio import export_pcm
            emit('exported', **export_pcm(Path(request['path']), Path(request['target']),
                                        request['start'], request['end']))
        else:
            raise ValueError('未知录音任务')
        return 0
    except Exception as exc:
        emit('error', message=str(exc))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
