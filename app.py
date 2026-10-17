"""
app.py - Main Flask application for Markify (PDF to Markdown web converter).
"""

import os
import uuid
from typing import List
from flask import (
    Flask, render_template, request, redirect, url_for,
    send_file, jsonify, flash, abort
)
from werkzeug.utils import secure_filename
import pymupdf as fitz

from converter import pdf_to_markdown, ScannedPDFError, ConversionError
from database import (
    init_db, save_conversion, get_conversion_by_id,
    get_conversions_by_ids, get_all_conversions, delete_conversion
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(BASE_DIR, "storage")
PDF_DIR = os.path.join(STORAGE_DIR, "pdfs")
MD_DIR = os.path.join(STORAGE_DIR, "markdown")

os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(MD_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB max file size

# Initialize database schema
init_db()


@app.errorhandler(413)
def request_entity_too_large(error):
    """Handles uploads exceeding 20 MB."""
    message = "File exceeds the 20 MB size limit. Please upload a smaller PDF."
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": False, "error": message}), 413
    flash(message, "error")
    return redirect(url_for("index"))


@app.route("/", methods=["GET"])
def index():
    """Landing page with clean centered upload form."""
    return render_template("index.html")


@app.route("/convert", methods=["POST"])
def convert():
    """
    Accepts one or more PDF files, validates them, converts each to Markdown,
    stores records in SQLite and files on disk, then returns redirection info.
    """
    uploaded_files = request.files.getlist("pdf_files")
    if not uploaded_files or all(f.filename == "" for f in uploaded_files):
        # Fallback check for single 'file' parameter
        single = request.files.get("file")
        if single and single.filename:
            uploaded_files = [single]
        else:
            msg = "Please select at least one PDF file to convert."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": False, "error": msg}), 400
            flash(msg, "error")
            return redirect(url_for("index"))

    converted_ids: List[str] = []
    conversion_errors: List[str] = []

    for file in uploaded_files:
        if not file or not file.filename:
            continue

        raw_filename = file.filename
        clean_name = os.path.basename(raw_filename).strip()

        # 1. Reject non-PDF files
        if not clean_name.lower().endswith(".pdf"):
            conversion_errors.append(f"'{clean_name}': Only PDF files (.pdf) are allowed.")
            continue

        # Generate unique storage filenames
        conversion_id = str(uuid.uuid4())
        pdf_filename = f"{conversion_id}.pdf"
        md_filename = f"{conversion_id}.md"

        pdf_path = os.path.join(PDF_DIR, pdf_filename)
        md_path = os.path.join(MD_DIR, md_filename)

        try:
            # Save uploaded PDF to storage
            file.save(pdf_path)

            # Check PDF validity and page count
            try:
                doc = fitz.open(pdf_path)
                page_count = len(doc)
                doc.close()
            except Exception:
                os.remove(pdf_path)
                conversion_errors.append(f"'{clean_name}': Invalid or corrupted PDF file.")
                continue

            # Convert PDF to Markdown
            markdown_content = pdf_to_markdown(pdf_path)

            # Save Markdown to storage
            with open(md_path, "w", encoding="utf-8") as md_file:
                md_file.write(markdown_content)

            # Save to SQLite database
            save_conversion(
                conversion_id=conversion_id,
                original_filename=clean_name,
                pdf_path=pdf_path,
                md_path=md_path,
                page_count=page_count
            )
            converted_ids.append(conversion_id)

        except ScannedPDFError as e:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            conversion_errors.append(f"'{clean_name}': {str(e)}")
        except Exception as e:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            if os.path.exists(md_path):
                os.remove(md_path)
            conversion_errors.append(f"'{clean_name}': Conversion failed - {str(e)}")

    # Check outcomes
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json

    if not converted_ids:
        err_msg = " | ".join(conversion_errors) if conversion_errors else "Failed to process files."
        if is_ajax:
            return jsonify({"success": False, "error": err_msg}), 400
        flash(err_msg, "error")
        return redirect(url_for("index"))

    first_id = converted_ids[0]
    batch_param = ",".join(converted_ids)
    redirect_url = url_for("result", conversion_id=first_id, batch=batch_param)

    if is_ajax:
        return jsonify({
            "success": True,
            "ids": converted_ids,
            "redirect_url": redirect_url,
            "warnings": conversion_errors if conversion_errors else []
        })

    if conversion_errors:
        flash("Some files could not be converted: " + " | ".join(conversion_errors), "warning")

    return redirect(redirect_url)


@app.route("/result/<conversion_id>", methods=["GET"])
def result(conversion_id: str):
    """
    Displays rendered Markdown preview, raw Markdown toggle,
    download options, and tabs for multi-file batches.
    """
    current_conv = get_conversion_by_id(conversion_id)
    if not current_conv:
        abort(404, description="Conversion not found.")

    # Read active Markdown content
    md_content = ""
    if os.path.exists(current_conv["md_path"]):
        with open(current_conv["md_path"], "r", encoding="utf-8") as f:
            md_content = f.read()

    # Determine batch items
    batch_param = request.args.get("batch", "").strip()
    if batch_param:
        batch_ids = [b.strip() for b in batch_param.split(",") if b.strip()]
        batch_conversions = get_conversions_by_ids(batch_ids)
        # Ensure current conversion is in batch if not already
        if not any(c["id"] == conversion_id for c in batch_conversions):
            batch_conversions.insert(0, current_conv)
    else:
        batch_conversions = [current_conv]

    # Prepare auto-download payload
    auto_download_list = []
    for c in batch_conversions:
        base_name = os.path.splitext(c["original_filename"])[0]
        auto_download_list.append({
            "id": c["id"],
            "filename": f"{base_name}.md",
            "url": url_for("download_md", conversion_id=c["id"])
        })

    return render_template(
        "result.html",
        conversion=current_conv,
        batch_conversions=batch_conversions,
        batch_param=batch_param,
        markdown_content=md_content,
        auto_download_list=auto_download_list
    )


@app.route("/download/md/<conversion_id>", methods=["GET"])
def download_md(conversion_id: str):
    """Downloads the generated Markdown file."""
    conv = get_conversion_by_id(conversion_id)
    if not conv or not os.path.exists(conv["md_path"]):
        abort(404, description="Markdown file not found.")

    stem = os.path.splitext(conv["original_filename"])[0]
    download_filename = f"{stem}.md"

    return send_file(
        conv["md_path"],
        as_attachment=True,
        download_name=download_filename,
        mimetype="text/markdown"
    )


@app.route("/download/pdf/<conversion_id>", methods=["GET"])
def download_pdf(conversion_id: str):
    """Downloads the original PDF file."""
    conv = get_conversion_by_id(conversion_id)
    if not conv or not os.path.exists(conv["pdf_path"]):
        abort(404, description="PDF file not found.")

    return send_file(
        conv["pdf_path"],
        as_attachment=True,
        download_name=conv["original_filename"],
        mimetype="application/pdf"
    )


@app.route("/history", methods=["GET"])
def history():
    """Lists past conversions, newest first."""
    all_conversions = get_all_conversions()
    return render_template("history.html", conversions=all_conversions)


@app.route("/delete/<conversion_id>", methods=["POST"])
def delete(conversion_id: str):
    """Deletes conversion record from DB and deletes both files from storage."""
    record = delete_conversion(conversion_id)
    if record:
        if os.path.exists(record["pdf_path"]):
            try:
                os.remove(record["pdf_path"])
            except OSError:
                pass
        if os.path.exists(record["md_path"]):
            try:
                os.remove(record["md_path"])
            except OSError:
                pass

    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return jsonify({"success": True, "message": "Conversion deleted successfully."})

    flash("Conversion deleted successfully.", "success")
    return redirect(url_for("history"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
