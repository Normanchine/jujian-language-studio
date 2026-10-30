"""Runs inside an external MinerU environment, never the bundled study runtime."""
import argparse
import os
import re
from pathlib import Path


def source_key_sections(text):
    """Recover only explicit numbered keys, never infer answers from prose."""
    lines = text.splitlines()
    header = re.compile(r'^\s*(?:answer\s+key|参考答案|正确答案|答案|正解)\s*[:：]?\s*$', re.I)
    pair = re.compile(r'\d{1,4}\s*[.．、)）:：-]?\s*[A-Fa-f](?![A-Za-z])')
    sections = []
    for i, line in enumerate(lines):
        if not header.fullmatch(line):
            continue
        rows = []
        for following in lines[i+1:]:
            if not following.strip():
                continue
            residue = pair.sub('', following)
            if pair.search(following) and not re.sub(r'[\s,，;；/|]+', '', residue):
                rows.append(following)
            else:
                break
        if rows:
            sections.append(line + '\n' + '\n'.join(rows))
    return sections


def preserve_pdf_source_keys(source, output, start, end):
    """MinerU can omit short key rows even when PDF text retains them."""
    import json
    import pypdfium2 as pdfium
    document = pdfium.PdfDocument(str(source))
    pages = []
    try:
        for index in range(start, min(len(document), end+1 if end is not None else len(document))):
            page = document[index]
            textpage = page.get_textpage()
            try:
                pages.append(textpage.get_text_range())
            finally:
                textpage.close(); page.close()
    finally:
        document.close()
    sections = source_key_sections('\n'.join(pages))
    files = list(Path(output).rglob('*.md'))
    if len(files) != 1 or not sections:
        return
    markdown = files[0].read_text(encoding='utf-8')
    normalize = lambda value: re.sub(r'[\s*_#]+', '', value).casefold()
    missing = [section for section in sections if normalize(section) not in normalize(markdown)]
    if missing:
        files[0].write_text(markdown.rstrip() + '\n\n' + '\n\n'.join(missing) + '\n', encoding='utf-8')
        (Path(output) / 'source-answer-key-recovery.json').write_text(json.dumps({
            'source': 'original_pdf_text_layer', 'start_page': start+1,
            'end_page': end+1 if end is not None else None, 'sections_preserved': len(missing)}, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--language', choices=['en', 'ja'], required=True)
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--end', type=int)
    parser.add_argument('--device', choices=['auto', 'cpu', 'cuda'], default='auto')
    args = parser.parse_args()
    source = Path(args.input)
    if source.suffix.lower() == '.epub':
        import ebooklib
        from ebooklib import epub
        import html2text
        book = epub.read_epub(str(source))
        converter = html2text.HTML2Text()
        converter.body_width = 0
        items = [book.get_item_with_id(entry[0] if isinstance(entry, (tuple, list)) else entry) for entry in book.spine]
        items = [item for item in items if item is not None and item.get_type() == ebooklib.ITEM_DOCUMENT
                 and not isinstance(item, epub.EpubNav)]
        text = '\n\n'.join(converter.handle(item.get_content().decode('utf-8')) for item in items)
        output = Path(args.output)
        output.mkdir(parents=True, exist_ok=True)
        (output / 'converted.md').write_text(text, encoding='utf-8')
        return
    if args.device != 'auto':
        os.environ['MINERU_DEVICE_MODE'] = args.device
    elif not os.environ.get('MINERU_DEVICE_MODE'):
        import torch
        if torch.cuda.is_available() and torch.cuda.mem_get_info()[0] < 3 * 1024**3:
            # Keep a loaded local language model intact instead of competing
            # for its VRAM. User can explicitly select CPU/GPU if desired.
            os.environ['MINERU_DEVICE_MODE'] = 'cpu'
            print('Low free VRAM: using CPU for document conversion.', flush=True)
    from mineru.cli.common import do_parse, read_fn
    do_parse(output_dir=args.output, pdf_file_names=[source.name], pdf_bytes_list=[read_fn(source)],
             p_lang_list=['japan' if args.language == 'ja' else 'en'], backend='pipeline', parse_method='auto',
             start_page_id=args.start, end_page_id=args.end,
             f_draw_layout_bbox=False, f_draw_span_bbox=False, f_dump_orig_pdf=False,
             f_dump_model_output=False, f_dump_md=True, f_dump_content_list=True)
    if source.suffix.lower() == '.pdf':
        preserve_pdf_source_keys(source, args.output, args.start, args.end)


if __name__ == '__main__':
    main()
