import hashlib
import json
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # collector/

from storage import sanitize_component, sanitize_filename, save_submission, update_mail_status


class SanitizeTests(unittest.TestCase):
    def test_path_traversal(self):
        self.assertEqual(sanitize_filename("../../etc/passwd"), "passwd")
        self.assertEqual(sanitize_filename("..\\..\\微信证明.zip"), "微信证明.zip")

    def test_control_chars_removed(self):
        self.assertEqual(sanitize_filename("bad\x01name.zip"), "badname.zip")

    def test_empty_falls_back(self):
        self.assertEqual(sanitize_filename(""), "unnamed")
        self.assertEqual(sanitize_filename("..."), "unnamed")

    def test_long_name_truncated_keeping_ext(self):
        result = sanitize_filename("a" * 200 + ".zip")
        self.assertEqual(len(result), 120 + len(".zip"))
        self.assertTrue(result.endswith(".zip"))

    def test_component_strips_slashes(self):
        self.assertEqual(sanitize_component("张/三"), "张三")
        self.assertEqual(sanitize_component(""), "未知")


class SaveSubmissionTests(unittest.TestCase):
    def setUp(self):
        import tempfile

        self.tmp = Path(tempfile.mkdtemp())
        self.inbox = self.tmp / "inbox"
        self.now = datetime(2026, 9, 29, 10, 30, 52)
        self.payload = b"fake-zip-bytes"

    def test_layout_and_meta(self):
        submission_id, meta, file_path, meta_path = save_submission(
            self.inbox,
            filename="微信证明.zip",
            data=self.payload,
            platform="wechat",
            name="张三",
            phone="13800001234",
            order_no="A-001",
            password="abc123",
            ip_hash="abcd1234",
            now=self.now,
        )
        self.assertEqual(submission_id, "20260929/103052_张三_1234")
        self.assertEqual(file_path, self.inbox / "20260929" / "103052_张三_1234" / "微信证明.zip")
        self.assertEqual(file_path.read_bytes(), self.payload)

        saved = json.loads(meta_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["password"], "abc123")
        self.assertEqual(saved["platform"], "wechat")
        self.assertEqual(saved["name"], "张三")
        self.assertEqual(saved["phone"], "13800001234")
        self.assertEqual(saved["order_no"], "A-001")
        self.assertEqual(saved["original_filename"], "微信证明.zip")
        self.assertEqual(saved["file_size"], len(self.payload))
        self.assertEqual(saved["sha256"], hashlib.sha256(self.payload).hexdigest())
        self.assertEqual(saved["received_at"], "2026-09-29T10:30:52")
        self.assertEqual(saved["ip_hash"], "abcd1234")
        self.assertEqual(saved["mail_status"], "pending")

    def test_same_second_collision_gets_suffix(self):
        kwargs = dict(
            filename="证明.zip", data=b"x", platform="alipay", name="张三",
            phone="13800001234", order_no="", password="p", ip_hash="h", now=self.now,
        )
        first, _, _, _ = save_submission(self.inbox, **kwargs)
        second, _, _, _ = save_submission(self.inbox, **kwargs)
        self.assertEqual(first, "20260929/103052_张三_1234")
        self.assertEqual(second, "20260929/103052_张三_1234_2")

    def test_duplicate_filename_in_same_dir(self):
        from storage import _unique_path

        directory = self.tmp / "d"
        directory.mkdir()
        (directory / "a.zip").write_bytes(b"1")
        path = _unique_path(directory, "a.zip")
        self.assertEqual(path.name, "a_2.zip")

    def test_update_mail_status(self):
        _, _, _, meta_path = save_submission(
            self.inbox, filename="a.zip", data=b"x", platform="wechat", name="张三",
            phone="13800001234", order_no="", password="p", ip_hash="h", now=self.now,
        )
        update_mail_status(meta_path, "sent")
        saved = json.loads(meta_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["mail_status"], "sent")


if __name__ == "__main__":
    unittest.main()
