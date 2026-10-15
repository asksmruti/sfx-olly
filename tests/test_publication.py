import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.check_release import check_archives, contains_credential, private_path


class PublicationTests(unittest.TestCase):
    def test_private_paths_are_rejected(self):
        for path in ("package/.env", "package/.env.production", "package/.pypirc",
                     "package/sfx_olly/_debug_msg.txt", "package/private.pfx",
                     "package/data/alerts.jsonl", "package/.vscode/settings.json"):
            with self.subTest(path=path):
                self.assertTrue(private_path(path))

    def test_public_example_and_license_are_allowed(self):
        for path in ("package/.env.example", "package/LICENSE", "sfx_olly/config.py"):
            self.assertFalse(private_path(path))

    def test_recognized_credentials_are_rejected_without_echoing_them(self):
        self.assertTrue(contains_credential(("pypi-" + "x" * 30).encode()))
        self.assertTrue(contains_credential(("SFX_TOKEN=" + "x" * 24).encode()))
        self.assertFalse(contains_credential(b"SFX_TOKEN=\nWEBHOOK_SHARED_SECRET=\n"))

    def test_archive_rejects_private_file_and_nonempty_example_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "sample.whl")
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("package/.env", "SFX_TOKEN=\n")
                archive.writestr(".env.example", "WEBHOOK_SHARED_SECRET=placeholder\n")
            issues = check_archives([path])
            self.assertEqual(len(issues), 2)
            self.assertIn("private file", issues[0])
            self.assertIn("blank secrets", issues[1])
