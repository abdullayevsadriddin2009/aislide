"""HF Storage Buckets (S3-mos) yordamchi funksiyalari testlari."""
import unittest
from unittest import mock

import config
import storage


def _settings(**values):
    base = {
        "HF_S3_ENDPOINT": "https://sadriddin2009.s3.hf.co",
        "HF_S3_BUCKET": "aibot",
        "HF_S3_ACCESS_KEY_ID": "HFAKtest",
        "HF_S3_SECRET_ACCESS_KEY": "secret",
        "HF_S3_PUBLIC_URL": "",
    }
    base.update(values)
    return mock.patch.multiple(config, **base)


class StorageTest(unittest.TestCase):
    def test_endpoint_parsed_as_path_style(self):
        with _settings():
            base, host, prefix = storage._endpoint()
        self.assertEqual(base, "https://sadriddin2009.s3.hf.co")
        self.assertEqual(host, "sadriddin2009.s3.hf.co")
        self.assertEqual(prefix, "")

    def test_public_url_has_no_revision(self):
        with _settings():
            url = storage.public_url("documents/12/esse.docx")
        self.assertEqual(
            url,
            "https://huggingface.co/buckets/sadriddin2009/aibot"
            "/resolve/documents/12/esse.docx",
        )

    def test_public_url_override_wins(self):
        with _settings(HF_S3_PUBLIC_URL="https://files.example.uz/bucket/"):
            self.assertEqual(storage.public_url("a/b.pdf"),
                             "https://files.example.uz/bucket/a/b.pdf")

    def test_namespace_prefixed_bucket_accepted(self):
        with _settings(HF_S3_BUCKET="sadriddin2009/aibot"):
            self.assertEqual(storage._bucket(), "aibot")
            self.assertIn("/buckets/sadriddin2009/aibot/", storage.public_url("x.txt"))

    def test_enabled_requires_all_parts(self):
        with _settings():
            self.assertTrue(storage.enabled())
        for field in ("HF_S3_ENDPOINT", "HF_S3_BUCKET",
                      "HF_S3_ACCESS_KEY_ID", "HF_S3_SECRET_ACCESS_KEY"):
            with _settings(**{field: ""}):
                self.assertFalse(storage.enabled(), field)


if __name__ == "__main__":
    unittest.main()
