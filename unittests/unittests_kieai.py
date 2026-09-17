import os
import unittest
import tempfile
from pathlib import Path

from .unittests import BaseTestCase

# Adjust this import based on your actual project structure
from genlab.main import KieAIGen


class TestKieAIGenRealUploadDownload(BaseTestCase):
    def setUp(self):
        """Set up the test environment by instantiating the API and creating temp files."""
        # Create a temporary directory to house our test files
        self.temp_dir = tempfile.TemporaryDirectory()

        # Initialize KieAIGen with the required params file
        self.kie = KieAIGen(Path(self.temp_dir.name))

        # 2. Set up paths for the upload/download test
        self.source_file_path = Path(self.temp_dir.name) / "sample.png"
        self.downloaded_file_path = Path(self.temp_dir.name) / "downloaded.png"

        # Write dummy binary data to simulate an image/file
        self.dummy_data = b"dummy file content for KieAIGen testing, ! blah blah **&&"
        with open(self.source_file_path, "wb") as f:
            f.write(self.dummy_data)

    def test_upload_and_download_file(self):
        """
        Tests the actual upload and download mechanisms of the Kie API.
        This operation does not use credits[cite: 1].
        """
        # 1. Test Upload
        # Upload the file and capture the resulting URL
        upload_url = self.kie.upload_file(self.source_file_path)

        # Assert that the upload was successful and returned a valid string URL
        self.assertIsNotNone(upload_url, "Upload failed to return a URL.")
        self.assertIsInstance(upload_url, str, "Upload URL should be a string.")
        self.assertTrue(upload_url.startswith("http"), "Upload URL is invalid.")

        # 2. Test Download
        # Download the file using the URL provided by the upload method
        self.kie.download_file(url=upload_url, output_path=str(self.downloaded_file_path))

        # Assert that the file actually exists at the targeted output path
        self.assertTrue(self.downloaded_file_path.exists(), "Downloaded file was not found on disk.")

        # 3. Verify Content Integrity
        # Ensure the downloaded file hasn't been corrupted or altered
        with open(self.downloaded_file_path, "rb") as f:
            downloaded_data = f.read()

        self.assertEqual(
            self.dummy_data,
            downloaded_data,
            "The downloaded file content does not match the originally uploaded file content."
        )

    def tearDown(self):
        """Clean up the temporary directory and files after the test runs."""
        self.temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()