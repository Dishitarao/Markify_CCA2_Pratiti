"""
converter.py - PDF to Markdown conversion engine for Markify.
Uses PyMuPDF (fitz) to extract text, font sizes, flags, and layout.
"""

import re
from collections import Counter
from typing import List, Dict, Any, Tuple, Optional
import pymupdf as fitz  # PyMuPDF



# ============================================================================
# TUNABLE THRESHOLDS & CONSTANTS
# ============================================================================
HEADING_MIN_SIZE_RATIO = 1.15      # Size >= body_size * 1.15 qualifies as heading
BOLD_HEADING_MIN_RATIO = 1.05      # Bold text with size >= body_size * 1.05 qualifies
MAX_HEADING_LEVEL = 4              # Headings capped at #### (#, ##, ###, ####)
HEADER_MARGIN_RATIO = 0.08         # Top 8% of page considered header region
FOOTER_MARGIN_RATIO = 0.08         # Bottom 8% of page considered footer region
REPEATED_TEXT_THRESHOLD = 0.5      # Appears in >= 50% of pages to be stripped
MAX_HEADING_CHAR_LENGTH = 120      # Headings shouldn't be excessively long paragraphs

# Bullet & Numbered list regex
BULLET_REGEX = re.compile(r'^[\s]*([•\-\*–—▪\u2022\u2023\u25E6\u2043\u2219\u25CF\u25CB\u00B7\uF0B7\uFFFD]|-\s+)\s*(.+)$')
NUMBERED_REGEX = re.compile(r'^[\s]*(?:(\d+)[\.\)]|\((\d+)\))\s*(.+)$')
PAGE_NUMBER_REGEX = re.compile(r'^(page\s+\d+(\s+of\s+\d+)?|\d+|-\s*\d+\s*-|\[\s*\d+\s*\])$', re.IGNORECASE)



class ConversionError(Exception):
    """Custom exception for conversion errors."""
    pass


class ScannedPDFError(ConversionError):
    """Exception raised when PDF has no extractable text."""
    pass


def is_bold(flags: int, font_name: str) -> bool:
    """Check if span is bold from PyMuPDF flags or font name."""
    if flags & 16:  # bit 4 = bold
        return True
    lower = font_name.lower()
    return any(w in lower for w in ("bold", "black", "heavy", "medium", "semibold", "demibold"))


def is_italic(flags: int, font_name: str) -> bool:
    """Check if span is italic from PyMuPDF flags or font name."""
    if flags & 2:  # bit 1 = italic
        return True
    lower = font_name.lower()
    return any(w in lower for w in ("italic", "oblique", "slanted"))


def analyze_document_typography(doc: fitz.Document) -> Tuple[float, List[float], set, set]:
    """
    Analyzes document font sizes and identifies:
    1. Body font size (most frequent by character count).
    2. Heading font sizes sorted descending.
    3. Repeated headers and footers across pages.
    """
    font_char_counts = Counter()
    total_text_length = 0

    page_count = len(doc)
    top_texts_per_page = []
    bottom_texts_per_page = []

    for page_idx in range(page_count):
        page = doc[page_idx]
        page_dict = page.get_text("dict")
        height = page_dict.get("height", 842)

        page_top_texts = set()
        page_bottom_texts = set()

        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:  # text blocks only
                continue

            for line in block.get("lines", []):
                line_text = "".join(span.get("text", "") for span in line.get("spans", [])).strip()
                if not line_text:
                    continue

                total_text_length += len(line_text)
                bbox = line.get("bbox", (0, 0, 0, 0))
                y0, y1 = bbox[1], bbox[3]

                # Check header / footer candidate
                if y0 < height * HEADER_MARGIN_RATIO:
                    page_top_texts.add(line_text)
                elif y1 > height * (1 - FOOTER_MARGIN_RATIO):
                    page_bottom_texts.add(line_text)

                for span in line.get("spans", []):
                    span_text = span.get("text", "").strip()
                    if span_text:
                        size = round(span.get("size", 10.0), 1)
                        font_char_counts[size] += len(span_text)

        top_texts_per_page.append(page_top_texts)
        bottom_texts_per_page.append(page_bottom_texts)

    # Scanned PDF check
    if total_text_length == 0 or not font_char_counts:
        raise ScannedPDFError("This PDF appears to be scanned or image-only. Text extraction isn't supported yet.")

    # Body size is the size with the highest character count
    body_size = font_char_counts.most_common(1)[0][0]

    # Detect heading sizes: noticeably larger than body_size
    heading_sizes = sorted(
        [size for size in font_char_counts.keys() if size >= body_size * HEADING_MIN_SIZE_RATIO],
        reverse=True
    )

    # Detect repeated headers & footers
    repeated_headers = set()
    repeated_footers = set()

    if page_count >= 2:
        top_counter = Counter(t for p in top_texts_per_page for t in p)
        bottom_counter = Counter(t for p in bottom_texts_per_page for t in p)
        min_occurrences = max(2, int(page_count * REPEATED_TEXT_THRESHOLD))

        for text, count in top_counter.items():
            if count >= min_occurrences:
                repeated_headers.add(text)

        for text, count in bottom_counter.items():
            if count >= min_occurrences:
                repeated_footers.add(text)

    return body_size, heading_sizes, repeated_headers, repeated_footers


def format_spans_in_line(spans: List[Dict[str, Any]], is_heading: bool = False) -> str:
    """
    Converts spans into a Markdown formatted line.
    Applies bold and italic formatting to non-heading spans.
    Merges adjacent formatted spans and preserves spaces cleanly.
    """
    if is_heading:
        # Strip all bold/italic markers from heading lines
        raw = "".join(span.get("text", "") for span in spans)
        return " ".join(raw.split())

    formatted_parts = []
    for span in spans:
        raw_text = span.get("text", "")
        if not raw_text:
            continue

        flags = span.get("flags", 0)
        font = span.get("font", "")
        bold = is_bold(flags, font)
        italic = is_italic(flags, font)

        if not (bold or italic):
            formatted_parts.append(raw_text)
            continue

        # Extract leading and trailing whitespace
        stripped = raw_text.strip()
        if not stripped:
            formatted_parts.append(raw_text)
            continue

        leading_ws = raw_text[:len(raw_text) - len(raw_text.lstrip())]
        trailing_ws = raw_text[len(raw_text.rstrip()):]

        if bold and italic:
            tag = "***"
        elif bold:
            tag = "**"
        else:
            tag = "*"

        formatted_parts.append(f"{leading_ws}{tag}{stripped}{tag}{trailing_ws}")

    line_str = "".join(formatted_parts)
    # Clean redundant markers like `** **` or adjacent `****`
    line_str = line_str.replace("****", "").replace("******", "")
    return line_str


def get_heading_level(avg_size: float, is_all_bold: bool, body_size: float, heading_sizes: List[float], line_len: int) -> Optional[int]:
    """
    Determines heading level (#, ##, ###, ####) or None if normal text.
    """
    if line_len > MAX_HEADING_CHAR_LENGTH:
        return None

    # Check if size is in detected heading sizes
    for rank, size in enumerate(heading_sizes):
        if abs(avg_size - size) <= 0.4:
            level = rank + 1
            return min(level, MAX_HEADING_LEVEL)

    # Size significantly larger than body
    if avg_size >= body_size * HEADING_MIN_SIZE_RATIO:
        if avg_size > body_size * 1.5:
            return 1
        elif avg_size > body_size * 1.3:
            return 2
        elif avg_size > body_size * 1.15:
            return 3
        else:
            return 4

    # Bold short line that is at least body size
    if is_all_bold and avg_size >= body_size * BOLD_HEADING_MIN_RATIO and line_len <= 80:
        return 4

    return None


def merge_hyphenated_lines(prev: str, curr: str) -> str:
    """
    Merges two lines, fixing hyphenated line breaks (e.g. 'exam-\nple' -> 'example').
    """
    # Check if previous line ends with a word and a hyphen
    match = re.search(r'([A-Za-z0-9]+)-\s*$', prev)
    if match:
        curr_match = re.match(r'^\s*([A-Za-z0-9]+)(.*)$', curr)
        if curr_match:
            # Reconstruct: remove hyphen and join seamlessly
            prefix = prev[:match.start()] + match.group(1) + curr_match.group(1)
            suffix = curr_match.group(2)
            return prefix + suffix

    return prev + " " + curr.strip()


def parse_page_to_markdown(
    page: fitz.Page,
    page_num: int,
    body_size: float,
    heading_sizes: List[float],
    repeated_headers: set,
    repeated_footers: set
) -> str:
    """Parses a single page's text blocks into Markdown."""
    page_dict = page.get_text("dict")
    height = page_dict.get("height", 842)

    page_elements: List[str] = []

    blocks = page_dict.get("blocks", [])
    # Sort blocks vertically by y0
    blocks = sorted([b for b in blocks if b.get("type") == 0], key=lambda b: b.get("bbox", (0, 0, 0, 0))[1])

    current_list_type: Optional[str] = None  # 'bullet' or 'numbered'

    for block in blocks:
        lines = block.get("lines", [])
        if not lines:
            continue

        block_lines: List[Dict[str, Any]] = []

        for line in lines:
            bbox = line.get("bbox", (0, 0, 0, 0))
            y0, y1 = bbox[1], bbox[3]
            spans = line.get("spans", [])
            raw_text = "".join(s.get("text", "") for s in spans).strip()

            if not raw_text:
                continue

            # Strip repeated headers, footers, and standalone page numbers
            is_top = y0 < height * HEADER_MARGIN_RATIO
            is_bottom = y1 > height * (1 - FOOTER_MARGIN_RATIO)

            if is_top and (raw_text in repeated_headers or PAGE_NUMBER_REGEX.match(raw_text)):
                continue
            if is_bottom and (raw_text in repeated_footers or PAGE_NUMBER_REGEX.match(raw_text)):
                continue

            # Compute average size and boldness of the line
            total_chars = sum(len(s.get("text", "").strip()) for s in spans) or 1
            avg_size = sum(s.get("size", 10.0) * len(s.get("text", "").strip()) for s in spans) / total_chars
            all_bold = all(is_bold(s.get("flags", 0), s.get("font", "")) for s in spans if s.get("text", "").strip())

            block_lines.append({
                "spans": spans,
                "raw_text": raw_text,
                "avg_size": avg_size,
                "all_bold": all_bold,
                "y0": y0,
                "y1": y1
            })

        if not block_lines:
            continue

        # Process lines within the block
        line_idx = 0
        while line_idx < len(block_lines):
            line_data = block_lines[line_idx]
            raw_text = line_data["raw_text"]
            avg_size = line_data["avg_size"]
            all_bold = line_data["all_bold"]
            spans = line_data["spans"]

            # 1. Heading check
            heading_level = get_heading_level(avg_size, all_bold, body_size, heading_sizes, len(raw_text))
            if heading_level is not None:
                # Heading line!
                heading_text = format_spans_in_line(spans, is_heading=True)
                # Strip existing leading #'s if any in text
                heading_text = heading_text.lstrip("#").strip()
                hashes = "#" * heading_level
                page_elements.append(f"{hashes} {heading_text}")
                current_list_type = None
                line_idx += 1
                continue

            # 2. Bullet list check
            bullet_match = BULLET_REGEX.match(raw_text)
            if bullet_match:
                item_content = bullet_match.group(2).strip()
                # Format spans inside list item
                formatted_line = format_spans_in_line(spans, is_heading=False)
                # Replace the bullet symbol at the start
                clean_item = BULLET_REGEX.sub(r"- \2", formatted_line).strip()

                # Collect continuation lines within the same block
                line_idx += 1
                while line_idx < len(block_lines):
                    next_line = block_lines[line_idx]
                    # Check if next line is a new bullet, numbered, or heading
                    if (BULLET_REGEX.match(next_line["raw_text"]) or
                        NUMBERED_REGEX.match(next_line["raw_text"]) or
                        get_heading_level(next_line["avg_size"], next_line["all_bold"], body_size, heading_sizes, len(next_line["raw_text"]))):
                        break

                    next_formatted = format_spans_in_line(next_line["spans"], is_heading=False)
                    clean_item = merge_hyphenated_lines(clean_item, next_formatted)
                    line_idx += 1

                page_elements.append(clean_item)
                current_list_type = "bullet"
                continue

            # 3. Numbered list check
            num_match = NUMBERED_REGEX.match(raw_text)
            if num_match:
                num = num_match.group(1) or num_match.group(2)
                item_content = num_match.group(3).strip()
                formatted_line = format_spans_in_line(spans, is_heading=False)
                # Convert to standard "1. item"
                clean_item = NUMBERED_REGEX.sub(rf"{num}. \3", formatted_line).strip()

                # Collect continuation lines
                line_idx += 1
                while line_idx < len(block_lines):
                    next_line = block_lines[line_idx]
                    if (BULLET_REGEX.match(next_line["raw_text"]) or
                        NUMBERED_REGEX.match(next_line["raw_text"]) or
                        get_heading_level(next_line["avg_size"], next_line["all_bold"], body_size, heading_sizes, len(next_line["raw_text"]))):
                        break

                    next_formatted = format_spans_in_line(next_line["spans"], is_heading=False)
                    clean_item = merge_hyphenated_lines(clean_item, next_formatted)
                    line_idx += 1

                page_elements.append(clean_item)
                current_list_type = "numbered"
                continue

            # 4. Standard Paragraph
            para_text = format_spans_in_line(spans, is_heading=False)
            line_idx += 1

            while line_idx < len(block_lines):
                next_line = block_lines[line_idx]
                if (BULLET_REGEX.match(next_line["raw_text"]) or
                    NUMBERED_REGEX.match(next_line["raw_text"]) or
                    get_heading_level(next_line["avg_size"], next_line["all_bold"], body_size, heading_sizes, len(next_line["raw_text"]))):
                    break

                next_formatted = format_spans_in_line(next_line["spans"], is_heading=False)
                para_text = merge_hyphenated_lines(para_text, next_formatted)
                line_idx += 1

            page_elements.append(para_text)
            current_list_type = None

    # Group elements into Markdown string:
    # Consecutive list items of same list type stay together with single newlines;
    # Switching between bullet/numbered or between paragraphs/headings gets blank lines (\n\n).
    md_output_lines: List[str] = []
    prev_list_type: Optional[str] = None

    for elem in page_elements:
        if elem.startswith("- "):
            current_type = "bullet"
        elif re.match(r'^\d+\.\s', elem):
            current_type = "numbered"
        else:
            current_type = None

        if current_type is not None:
            if prev_list_type != current_type and md_output_lines:
                md_output_lines.append("")
            md_output_lines.append(elem)
            prev_list_type = current_type
        else:
            if md_output_lines:
                md_output_lines.append("")
            md_output_lines.append(elem)
            prev_list_type = None

    return "\n".join(md_output_lines).strip()



def pdf_to_markdown(pdf_path: str) -> str:
    """
    Main conversion function: reads PDF from `pdf_path` and returns Markdown string.
    
    Preserves:
    - Headings (#, ##, ###, ####)
    - Paragraphs with hyphenation repair
    - Bulleted lists (- item) and numbered lists (1. item) with continuation lines
    - Bold (**text**) and italic (*text*) formatting
    - Page breaks (---) and page comments (<!-- Page N -->)
    - Repeated header/footer and standalone page number suppression
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        raise ConversionError(f"Failed to open PDF file: {str(e)}")

    try:
        if len(doc) == 0:
            raise ScannedPDFError("This PDF appears to be scanned or image-only. Text extraction isn't supported yet.")

        body_size, heading_sizes, repeated_headers, repeated_footers = analyze_document_typography(doc)

        page_markdowns: List[str] = []
        for page_idx in range(len(doc)):
            page_num = page_idx + 1
            page = doc[page_idx]
            page_md = parse_page_to_markdown(
                page=page,
                page_num=page_num,
                body_size=body_size,
                heading_sizes=heading_sizes,
                repeated_headers=repeated_headers,
                repeated_footers=repeated_footers
            )

            # Insert HTML comment for page
            page_block = f"<!-- Page {page_num} -->\n{page_md}" if page_md else f"<!-- Page {page_num} -->"
            page_markdowns.append(page_block)

        # Separate pages with horizontal rule (---)
        full_markdown = "\n\n---\n\n".join(page_markdowns).strip() + "\n"
        return full_markdown
    finally:
        doc.close()
