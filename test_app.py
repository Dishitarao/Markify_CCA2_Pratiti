
"""
Integration tests for Markify with S3-backed file storage.
"""

import os
import io
import unittest
from unittest.mock import patch

from app import app, S3_BUCKET
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

        # Mock S3 so tests don't require AWS credentials or create real objects.
        self.s3_patcher = patch("app.s3")
        self.mock_s3 = self.s3_patcher.start()
        self.addCleanup(self.s3_patcher.stop)

        self.s3_objects = {}

        def fake_upload_file(filename, bucket, key):
            with open(filename, "rb") as file_obj:
                self.s3_objects[key] = file_obj.read()

        def fake_get_object(Bucket, Key):
            if Key not in self.s3_objects:
                from botocore.exceptions import ClientError
                raise ClientError(
                    {
                        "Error": {
                            "Code": "NoSuchKey",
                            "Message": "Object not found",
                        }
                    },
                    "GetObject",
                )

            return {"Body": io.BytesIO(self.s3_objects[Key])}

        def fake_delete_object(Bucket, Key):
            self.s3_objects.pop(Key, None)
            return {}

        self.mock_s3.upload_file.side_effect = fake_upload_file
        self.mock_s3.get_object.side_effect = fake_get_object
        self.mock_s3.delete_object.side_effect = fake_delete_object

    def test_01_landing_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")
        self.assertIn("Welcome to Markify", html)
        self.assertIn("Enter", html)
        self.assertIn("upload-form", html)

    def test_02_convert_single_pdf(self):
        with open(self.sample_pdf_path, "rb") as file_obj:
            pdf_bytes = file_obj.read()

        response = self.client.post(
            "/convert",
            data={"pdf_files": (io.BytesIO(pdf_bytes), "sample.pdf")},
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertTrue(json_data["success"])
        self.assertEqual(len(json_data["ids"]), 1)

        conv_id = json_data["ids"][0]
        record = get_conversion_by_id(conv_id)

        self.assertIsNotNone(record)
        self.assertEqual(record["original_filename"], "sample.pdf")
        self.assertEqual(record["page_count"], 2)
        self.assertTrue(record["pdf_path"].startswith(f"s3://{S3_BUCKET}/"))
        self.assertTrue(record["md_path"].startswith(f"s3://{S3_BUCKET}/"))

        pdf_key = record["pdf_path"].replace(f"s3://{S3_BUCKET}/", "")
        md_key = record["md_path"].replace(f"s3://{S3_BUCKET}/", "")

        self.assertIn(pdf_key, self.s3_objects)
        self.assertIn(md_key, self.s3_objects)

        markdown = self.s3_objects[md_key].decode("utf-8")
        self.assertIn("# Comprehensive Markdown Guide", markdown)
        self.assertIn("## Introduction and Overview", markdown)
        self.assertIn("1. First step", markdown)
        self.assertIn("<!-- Page 1 -->", markdown)
        self.assertIn("<!-- Page 2 -->", markdown)

        result_response = self.client.get(f"/result/{conv_id}")
        self.assertEqual(result_response.status_code, 200)
        self.assertIn(
            "Comprehensive Markdown Guide",
            result_response.data.decode("utf-8"),
        )

        download_response = self.client.get(f"/download/md/{conv_id}")
        self.assertEqual(download_response.status_code, 200)
        self.assertIn(
            b"Comprehensive Markdown Guide",
            download_response.data,
        )

        pdf_response = self.client.get(f"/download/pdf/{conv_id}")
        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response.data, pdf_bytes)

        delete_response = self.client.post(
            f"/delete/{conv_id}",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertIsNone(get_conversion_by_id(conv_id))
        self.assertNotIn(pdf_key, self.s3_objects)
        self.assertNotIn(md_key, self.s3_objects)

    def test_03_reject_non_pdf(self):
        response = self.client.post(
            "/convert",
            data={"pdf_files": (io.BytesIO(b"Hello non-pdf"), "document.txt")},
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        self.assertEqual(response.status_code, 400)
        json_data = response.get_json()
        self.assertFalse(json_data["success"])
        self.assertIn(
            "Only PDF files (.pdf) are allowed",
            json_data["error"],
        )

    def test_04_reject_scanned_pdf(self):
        with open(self.blank_pdf_path, "rb") as file_obj:
            pdf_bytes = file_obj.read()

        response = self.client.post(
            "/convert",
            data={"pdf_files": (io.BytesIO(pdf_bytes), "blank.pdf")},
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        self.assertEqual(response.status_code, 400)
        json_data = response.get_json()
        self.assertFalse(json_data["success"])
        self.assertIn("scanned or image-only", json_data["error"])

    def test_05_convert_multiple_pdfs(self):
        with open(self.sample_pdf_path, "rb") as file_obj:
            pdf_bytes = file_obj.read()

        response = self.client.post(
            "/convert",
            data={
                "pdf_files": [
                    (io.BytesIO(pdf_bytes), "batch1.pdf"),
                    (io.BytesIO(pdf_bytes), "batch2.pdf"),
                ]
            },
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertTrue(json_data["success"])
        self.assertEqual(len(json_data["ids"]), 2)

        result_response = self.client.get(json_data["redirect_url"])
        self.assertEqual(result_response.status_code, 200)
        html = result_response.data.decode("utf-8")
        self.assertIn("batch1.pdf", html)
        self.assertIn("batch2.pdf", html)

        for conv_id in json_data["ids"]:
            record = get_conversion_by_id(conv_id)
            self.assertIsNotNone(record)

            pdf_key = record["pdf_path"].replace(f"s3://{S3_BUCKET}/", "")
            md_key = record["md_path"].replace(f"s3://{S3_BUCKET}/", "")

            self.client.post(
                f"/delete/{conv_id}",
                headers={"X-Requested-With": "XMLHttpRequest"},
            )

            self.assertNotIn(pdf_key, self.s3_objects)
            self.assertNotIn(md_key, self.s3_objects)


if __name__ == "__main__":
    unittest.main()
