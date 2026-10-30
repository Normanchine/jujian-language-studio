"""Local MinerU subprocess and direct Markdown/text loading."""
from __future__ import annotations
import os
from pathlib import Path
import re
import subprocess
import time

from core.paths import ASSETS

MAX_FILE = 200 * 1024 * 1024
TEXT_TYPES = {'.md', '.markdown', '.txt'}
DOCUMENT_TYPES = {'.pdf', '.docx', '.pptx', '.epub', '.png', '.jpg', '.jpeg', '.webp', '.bmp'}


class ConversionCancelled(Exception):
    pass


def check_cancel(cancel):
    if cancel.is_set():
        raise ConversionCancelled('已取消，源文件未改变')


def read_markdown(path):
    path = Path(path)
    if path.stat().st_size > 2_000_000:
        raise ValueError('文本超过 2 MB，请按单元拆分后导入')
    value = path.read_bytes()
    codec = 'utf-16' if value.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
    try:
        result = value.decode(codec)
    except UnicodeError as exc:
        raise ValueError('文本编码无法识别，请另存为 UTF-8') from exc
    if '\x00' in result or not result.strip():
        raise ValueError('文件不是有效的文本内容')
    return result


def page_range(value):
    value = value.strip()
    if not value:
        return None, None
    match = re.fullmatch(r'([1-9]\d*)(?:\s*-\s*([1-9]\d*))?', value)
    if not match:
        raise ValueError('页码请输入 3 或 3-12，留空转换全部')
    start, end = int(match[1]), int(match[2] or match[1])
    if start > end or end > 10000:
        raise ValueError('页码范围无效')
    return start - 1, end - 1


def local_convert(path, output, python, language, pages, cancel, progress, device='auto'):
    executable = Path(python).expanduser()
    if not executable.is_file():
        raise ValueError('未找到 MinerU 的 Python，请选择已安装 MinerU 的环境（例如 F:/MinerU/venv/Scripts/python.exe）')
    command = [str(executable), '-u', str(ASSETS / 'helpers/mineru_convert.py'),
               '--input', str(path), '--output', str(output), '--language', language, '--device', device]
    start, end = page_range(pages)
    if start is not None:
        command += ['--start', str(start), '--end', str(end)]
    progress('本地 MinerU 正在转换，首次加载模型可能较慢…')
    output.mkdir(parents=True, exist_ok=True)
    # Full diagnostics stay local; no shell expansion, console window or input().
    environment = os.environ.copy()
    cache = Path(environment.get('HF_HOME', str(Path.home() / '.cache/huggingface'))) / 'hub/models--opendatalab--PDF-Extract-Kit-1.0'
    prefer_cached = 'HF_HUB_OFFLINE' not in environment and cache.is_dir()
    environments = [{**environment, 'HF_HUB_OFFLINE': '1'}, environment] if prefer_cached else [environment]
    for attempt, child_environment in enumerate(environments):
        with (output / 'conversion.log').open('ab' if attempt else 'wb') as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=child_environment,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            deadline = time.monotonic() + 3600
            try:
                while process.poll() is None:
                    check_cancel(cancel)
                    if time.monotonic() >= deadline:
                        raise ValueError('本地转换超时，请缩小页码范围')
                    cancel.wait(0.15)
            finally:
                if process.poll() is None:
                    if os.name == 'nt':
                        # Only the owned helper's tree, including its renderers.
                        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       creationflags=subprocess.CREATE_NO_WINDOW, timeout=3)
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
        if process.returncode == 0:
            break
        log_text = (output / 'conversion.log').read_text(encoding='utf-8', errors='replace').lower()
        cache_missing = any(marker in log_text for marker in ('localentrynotfounderror', 'offlinemodeisenabled',
            'cached snapshot', 'local cache', 'outgoing traffic'))
        if attempt == 0 and prefer_cached and cache_missing:
            progress('本地模型缓存不完整，正在尝试下载缺失模型（不会上传文档）…')
            continue
        raise ValueError('本地 MinerU 转换失败；请检查环境、模型与文档。诊断日志：' + str(output / 'conversion.log'))
    files = sorted(output.rglob('*.md'))
    if len(files) != 1:
        raise ValueError('MinerU 未输出唯一 Markdown，请检查本地转换日志')
    return read_markdown(files[0])


def convert_document(path, output, mode, python, language, pages, cancel, progress, device='auto'):
    path = Path(path)
    if path.suffix.lower() in TEXT_TYPES:
        return read_markdown(path)
    if path.suffix.lower() not in DOCUMENT_TYPES:
        raise ValueError('支持 MD/TXT、PDF、DOCX、PPTX、EPUB 和常见图片；其他格式请先转为 MD')
    if path.stat().st_size > MAX_FILE:
        raise ValueError('文档超过 200 MB，请拆分后导入')
    if pages.strip() and path.suffix.lower() != '.pdf':
        raise ValueError('页码范围仅用于 PDF，其他文件请留空')
    if mode == 'local':
        return local_convert(path, Path(output), python, language, pages, cancel, progress, device)
    raise ValueError('文档转换仅支持本地 MinerU；也可直接导入已有 MD/TXT')
