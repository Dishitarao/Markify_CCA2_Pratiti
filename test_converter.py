"""
test_converter.py - Test script for converter.py
Creates sample PDFs using PyMuPDF and validates Markdown conversion.
"""

import os
import pymupdf as fitz
from converter import pdf_to_markdown, ScannedPDFError

def create_sample_pdf(filename: str):
    doc = fitz.open()

    # --- Page 1 ---
    page1 = doc.new_page(width=595, height=842) # A4 size

    # Repeated header
    page1.insert_text((50, 40), "Markify Test Document - Confidential", fontsize=8, fontname="helv")

    # Document Title (# Heading 1)
    page1.insert_text((50, 100), "Comprehensive Markdown Guide", fontsize=24, fontname="hebo")

    # Section Heading (## Heading 2)
    page1.insert_text((50, 150), "Introduction and Overview", fontsize=18, fontname="hebo")

    # Paragraph with regular, bold, and italic text using insert_text spans
    # Line 1:
    page1.insert_text((50, 175), "Markify is a ", fontsize=11, fontname="tiro")
    page1.insert_text((115, 175), "powerful conversion tool", fontsize=11, fontname="tibo") # bold
    page1.insert_text((245, 175), " designed to deliver ", fontsize=11, fontname="tiro")
    page1.insert_text((350, 175), "flawless results", fontsize=11, fontname="tiit") # italic
    page1.insert_text((428, 175), " every time.", fontsize=11, fontname="tiro")

    # Sub-heading (### Heading 3)
    page1.insert_text((50, 220), "Key Features", fontsize=14, fontname="hebo")

    # Bulleted list with continuation line
    page1.insert_text((50, 250), "• First bullet point highlighting fast processing and seamless operation", fontsize=11, fontname="tiro")
    page1.insert_text((65, 265), "with continuation lines properly handled.", fontsize=11, fontname="tiro")
    page1.insert_text((50, 290), "• Second bullet point with bold emphasis.", fontsize=11, fontname="tiro")
    page1.insert_text((50, 315), "• Third bullet point for testing.", fontsize=11, fontname="tiro")

    # Numbered list
    page1.insert_text((50, 355), "1. First step: upload your PDF file.", fontsize=11, fontname="tiro")
    page1.insert_text((50, 380), "2. Second step: converter analyzes font styles and structure.", fontsize=11, fontname="tiro")
    page1.insert_text((50, 405), "3. Third step: enjoy your clean Markdown document.", fontsize=11, fontname="tiro")


    # Repeated footer and page number
    page1.insert_text((50, 810), "Markify Conversion System © 2026", fontsize=8, fontname="helv")
    page1.insert_text((520, 810), "1", fontsize=9, fontname="helv")

    # --- Page 2 ---
    page2 = doc.new_page(width=595, height=842)

    # Repeated header
    page2.insert_text((50, 40), "Markify Test Document - Confidential", fontsize=8, fontname="helv")

    # Sub-sub-heading (#### Heading 4)
    page2.insert_text((50, 100), "Advanced Typography Handling", fontsize=12, fontname="hebo")

    # Paragraph with mixed styles
    p2 = ("The conversion engine intelligently reconstructs paragraphs, extracts headings, "
          "detects lists, and eliminates unwanted headers and footers.")
    page2.insert_textbox(fitz.Rect(50, 120, 545, 180), p2, fontsize=11, fontname="tiro")

    # Repeated footer and page number
    page2.insert_text((50, 810), "Markify Conversion System © 2026", fontsize=8, fontname="helv")
    page2.insert_text((520, 810), "2", fontsize=9, fontname="helv")

    doc.save(filename)
    doc.close()
    print(f"Sample PDF created: {filename}")

def create_blank_pdf(filename: str):
    doc = fitz.open()
    doc.new_page(width=595, height=842)
    doc.save(filename)
    doc.close()
    print(f"Blank PDF created: {filename}")

if __name__ == "__main__":
    os.makedirs("test_data", exist_ok=True)
    sample_pdf = "test_data/sample.pdf"
    blank_pdf = "test_data/blank.pdf"
    create_sample_pdf(sample_pdf)
    create_blank_pdf(blank_pdf)

    print("\n--- Testing sample.pdf conversion ---")
    md_result = pdf_to_markdown(sample_pdf)
    print("OUTPUT MARKDOWN:\n" + "="*40)
    print(md_result)
    print("="*40)

    print("\n--- Testing blank.pdf conversion (expect ScannedPDFError) ---")
    try:
        pdf_to_markdown(blank_pdf)
        print("ERROR: Should have raised ScannedPDFError!")
    except ScannedPDFError as e:
        print(f"SUCCESS: Caught expected ScannedPDFError: {e}")
