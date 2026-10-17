# Markify 📄 ➔ 📝

A clean, minimalist web application built with Python and Flask that converts PDF documents into beautifully structured Markdown files.

---

## Features

- **Accurate Heading Hierarchy**: Analyzes document typography using PyMuPDF to extract body font size, mapping larger and bold lines to `#`, `##`, `###`, and `####` (capped at level 4).
- **Paragraph & Line Reconstruction**: Merges consecutive lines into unified paragraphs, resolving hyphenated line breaks (e.g. `exam-\nple` ➔ `example`).
- **List Detection**: Recognizes bullet lists (`•`, `-`, `*`, `–`, `▪`, etc.) and numbered lists (`1.`, `1)`, `(1)`), preserving wrapped continuation lines.
- **Bold & Italic Formatting**: Identifies font weight and style flags to wrap non-heading spans with `**bold**` and `*italic*`.
- **Page Break Comments**: Adds horizontal rules (`---`) and page comment markers (`<!-- Page N -->`) between pages.
- **Header & Footer Stripping**: Eliminates repeating headers, footers, and standalone page numbers across multi-page documents.
- **Single & Multi-File Support**: Convert a single PDF or multiple PDFs at once. Result page displays preview tabs and auto-triggers downloading of each `.md` file.
- **Scanned PDF Detection**: Accurately detects image-only or scanned PDFs and notifies the user with a friendly error message.
- **Conversion History**: View all previous conversions ordered newest first, preview them, re-download PDFs or Markdown files, or delete them along with their stored files.

---

## Tech Stack

- **Backend**: Python 3.12+, Flask 3.x
- **PDF Extraction**: PyMuPDF (`fitz` / `pymupdf`) using span-level dictionary parsing (`page.get_text("dict")`)
- **Database**: SQLite (via `database.py`) storing conversion metadata
- **Disk Storage**: `storage/pdfs/` and `storage/markdown/`
- **Frontend**: Plain HTML5, CSS3, and Vanilla JavaScript with Jinja2 templates (no heavyweight JS frameworks)
- **Markdown Rendering**: [marked.js](https://marked.js.org/) via CDN

---

## Design System

- **Background**: Light neutral cream white (`#FAF7F2`)
- **Accent Color**: Deep forest green (`#2D6A4F` primary, `#1B4332` hover)
- **Typography**: System serif stack (*Times New Roman*, Times, serif) with italicized *"Welcome to Markify"* headline
- **Components**: Pill-rounded buttons, subtle soft shadows on cards, and clean typography for rendered Markdown

---

## Installation & Running

### 1. Prerequisites
Ensure Python 3.10+ is installed on your system.

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Start the Application
```bash
python app.py
```

Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---

## Project Structure

```
markify/
├── app.py                  # Main Flask routes, file upload, download & deletion handlers
├── converter.py            # PDF to Markdown parsing engine using PyMuPDF
├── database.py             # SQLite database layer for metadata management
├── test_converter.py       # Standalone test script for converter engine
├── requirements.txt        # Python package dependencies
├── README.md               # Documentation and run instructions
├── .gitignore              # Git ignore rules (ignores /storage/)
├── static/
│   └── css/
│       └── style.css       # Custom stylesheet (cream white & green theme, Times New Roman)
├── templates/
│   ├── base.html           # Base layout with navbar and footer
│   ├── index.html          # Landing page with centered upload card and loading state
│   ├── result.html         # Preview page with Marked.js rendering, raw view toggle & auto-download
│   └── history.html        # History table listing all past conversions with actions
└── storage/                # Local file storage (created automatically)
    ├── markify.db          # SQLite database
    ├── pdfs/               # Stored uploaded PDF files (UUID-based names)
    └── markdown/           # Stored generated Markdown files (UUID-based names)
```

---

## Core Routes

| Method | Route | Description |
|---|---|---|
| `GET` | `/` | Landing page with upload form and Enter button |
| `POST` | `/convert` | Handles file upload(s), runs conversion, and returns redirect data |
| `GET` | `/result/<id>` | Displays rendered Markdown preview, raw view toggle, and batch tabs |
| `GET` | `/download/md/<id>` | Downloads generated `.md` file named after original PDF |
| `GET` | `/download/pdf/<id>` | Downloads original uploaded PDF file |
| `GET` | `/history` | Conversion history page with actions (preview, download, delete) |
| `POST` | `/delete/<id>` | Deletes conversion from SQLite and removes files from disk |

---

## Running Standalone Tests

You can run the standalone conversion test anytime without starting Flask:
```bash
python test_converter.py
```
This script creates synthetic single-page and multi-page PDFs with headings, paragraphs, lists, bold/italic fonts, and repeated headers/footers to verify formatting and output integrity.
