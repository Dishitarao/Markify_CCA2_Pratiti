"""
test_app.py - Integration test suite for Markify web application.
Uses standard library unittest so it runs anywhere without extra dependencies.
"""

import os
import io
import unittest
from app import app
from database import init_db, get_conversion_by_id
from test_converter import create_sample_pdf, create_blank_pdf

class MarkifyAppTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.makedirs("test_data", exist_ok=True)
        cls.sample_pdf_path = "test_data/sample.pdf"
        cls.blank_pdf_path = "test_data/blank.pdf"
        if not os.path.exists(cls.sample_pdf_path):
            create_sample_pdf(cls.sample_pdf_path)
        if not os.path.exists(cls.blank_pdf_path):
            create_blank_pdf(cls.blank_pdf_path)

    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        with app.app_context():
            init_db()

    def test_01_landing_page(self):
        """Test landing page renders properly."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")
        self.assertIn("Welcome to Markify", html)
        self.assertIn("Enter", html)
        self.assertIn("upload-form", html)

    def test_02_convert_single_pdf(self):
        """Test converting a single valid PDF."""
        with open(self.sample_pdf_path, "rb") as f:
            pdf_bytes = f.read()

        data = {
            "pdf_files": (io.BytesIO(pdf_bytes), "sample.pdf")
        }
        response = self.client.post(
            "/convert",
            data=data,
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest"}
        )

        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertTrue(json_data["success"])
        self.assertEqual(len(json_data["ids"]), 1)
        conv_id = json_data["ids"][0]

        # Verify database record
        record = get_conversion_by_id(conv_id)
        self.assertIsNotNone(record)
        self.assertEqual(record["original_filename"], "sample.pdf")
        self.assertEqual(record["page_count"], 2)
        self.assertTrue(os.path.exists(record["pdf_path"]))
        self.assertTrue(os.path.exists(record["md_path"]))

        # Verify Markdown content on disk
        with open(record["md_path"], "r", encoding="utf-8") as f:
            md = f.read()
        self.assertIn("# Comprehensive Markdown Guide", md)
        self.assertIn("## Introduction and Overview", md)
        self.assertIn("1. First step", md)
        self.assertIn("<!-- Page 1 -->", md)
        self.assertIn("<!-- Page 2 -->", md)

        # Verify result preview page
        res_page = self.client.get(f"/result/{conv_id}")
        self.assertEqual(res_page.status_code, 200)
        self.assertIn("Comprehensive Markdown Guide", res_page.data.decode("utf-8"))

        # Verify file downloads
        md_dl = self.client.get(f"/download/md/{conv_id}")
        self.assertEqual(md_dl.status_code, 200)
        self.assertIn("sample.md", md_dl.headers.get("Content-Disposition", ""))
        md_dl.close()

        pdf_dl = self.client.get(f"/download/pdf/{conv_id}")
        self.assertEqual(pdf_dl.status_code, 200)
        self.assertIn("sample.pdf", pdf_dl.headers.get("Content-Disposition", ""))
        pdf_dl.close()


        # Verify history list
        hist_page = self.client.get("/history")
        self.assertEqual(hist_page.status_code, 200)
        self.assertIn("sample.pdf", hist_page.data.decode("utf-8"))

        # Verify deletion
        del_res = self.client.post(f"/delete/{conv_id}", headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(del_res.status_code, 200)
        self.assertIsNone(get_conversion_by_id(conv_id))
        self.assertFalse(os.path.exists(record["pdf_path"]))
        self.assertFalse(os.path.exists(record["md_path"]))

    def test_03_reject_non_pdf(self):
        """Test rejecting non-PDF file."""
        data = {
            "pdf_files": (io.BytesIO(b"Hello non-pdf"), "document.txt")
        }
        response = self.client.post(
            "/convert",
            data=data,
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest"}
        )
        self.assertEqual(response.status_code, 400)
        json_data = response.get_json()
        self.assertFalse(json_data["success"])
        self.assertIn("Only PDF files (.pdf) are allowed", json_data["error"])

    def test_04_reject_scanned_pdf(self):
        """Test scanned/blank PDF gives proper error."""
        with open(self.blank_pdf_path, "rb") as f:
            pdf_bytes = f.read()

        data = {
            "pdf_files": (io.BytesIO(pdf_bytes), "blank.pdf")
        }
        response = self.client.post(
            "/convert",
            data=data,
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest"}
        )
        self.assertEqual(response.status_code, 400)
        json_data = response.get_json()
        self.assertFalse(json_data["success"])
        self.assertIn("scanned or image-only", json_data["error"])

    def test_05_convert_multiple_pdfs(self):
        """Test batch conversion with multiple PDF files."""
        with open(self.sample_pdf_path, "rb") as f:
            pdf_bytes = f.read()

        data = {
            "pdf_files": [
                (io.BytesIO(pdf_bytes), "batch1.pdf"),
                (io.BytesIO(pdf_bytes), "batch2.pdf")
            ]
        }
        response = self.client.post(
            "/convert",
            data=data,
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest"}
        )
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertTrue(json_data["success"])
        self.assertEqual(len(json_data["ids"]), 2)

        # Check batch result page shows tabs
        batch_url = json_data["redirect_url"]
        res_page = self.client.get(batch_url)
        self.assertEqual(res_page.status_code, 200)
        html = res_page.data.decode("utf-8")
        self.assertIn("batch1.pdf", html)
        self.assertIn("batch2.pdf", html)

        # Cleanup
        for cid in json_data["ids"]:
            self.client.post(f"/delete/{cid}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
