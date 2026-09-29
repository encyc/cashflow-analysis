import email
import email.policy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # collector/

from config import Config
from mailer import build_message, send_submission_mail


def make_config(tmp: Path, attach_limit_mb: int = 45) -> Config:
    return Config(
        inbox_dir=tmp / "inbox",
        outbox_dir=tmp / "outbox",
        mail_attach_limit_mb=attach_limit_mb,
    )


def make_meta() -> dict:
    return {
        "submission_id": "20260929/103052_张三_1234",
        "platform": "wechat",
        "name": "张三",
        "phone": "13800001234",
        "order_no": "",
        "password": "We12!@解压",
        "original_filename": "微信证明.zip",
        "file_size": 2048,
        "sha256": "deadbeef" * 8,
        "received_at": "2026-09-29T10:30:52",
        "ip_hash": "abcd1234",
        "mail_status": "pending",
    }


class BuildMessageTests(unittest.TestCase):
    def setUp(self):
        import tempfile

        self.tmp = Path(tempfile.mkdtemp())
        self.file_path = self.tmp / "微信证明.zip"
        self.file_path.write_bytes(b"fake-zip-content")

    def test_subject_and_headers(self):
        msg = build_message(make_config(self.tmp), make_meta(), self.file_path)
        self.assertEqual(msg["Subject"], "【流水采集】张三-微信-0929 10:30")
        self.assertEqual(msg["To"], "")

    def test_body_contains_fields_password_once(self):
        msg = build_message(make_config(self.tmp), make_meta(), self.file_path)
        body = msg.get_body(preferencelist=("plain",)).get_content()
        meta = make_meta()
        self.assertEqual(body.count(meta["password"]), 1)
        for expected in (meta["name"], meta["phone"], "（未填写）", "微信", meta["sha256"], meta["submission_id"]):
            self.assertIn(expected, body)

    def test_attachment_present(self):
        msg = build_message(make_config(self.tmp), make_meta(), self.file_path)
        attachments = list(msg.iter_attachments())
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].get_filename(), "微信证明.zip")
        self.assertEqual(attachments[0].get_payload(decode=True), b"fake-zip-content")

    def test_no_attachment_hint(self):
        msg = build_message(make_config(self.tmp), make_meta(), None)
        self.assertEqual(list(msg.iter_attachments()), [])
        self.assertIn("超过邮件附件上限", msg.get_body(preferencelist=("plain",)).get_content())


class SendTests(unittest.TestCase):
    def setUp(self):
        import tempfile

        self.tmp = Path(tempfile.mkdtemp())
        self.file_path = self.tmp / "微信证明.zip"
        self.file_path.write_bytes(b"fake-zip-content")

    def test_dry_run_writes_eml(self):
        cfg = make_config(self.tmp)
        status = send_submission_mail(cfg, make_meta(), self.file_path)
        self.assertEqual(status, "dry-run")
        eml_path = cfg.outbox_dir / "20260929_103052_张三_1234.eml"
        self.assertTrue(eml_path.is_file())
        parsed = email.message_from_bytes(eml_path.read_bytes(), policy=email.policy.default)
        self.assertEqual(parsed["Subject"], "【流水采集】张三-微信-0929 10:30")
        attachments = list(parsed.iter_attachments())
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].get_payload(decode=True), b"fake-zip-content")

    def test_oversize_file_not_attached(self):
        big = self.tmp / "big.zip"
        big.write_bytes(b"x" * (1024 * 1024 + 100))
        cfg = make_config(self.tmp, attach_limit_mb=1)
        status = send_submission_mail(cfg, make_meta(), big)
        self.assertEqual(status, "dry-run")
        eml_path = cfg.outbox_dir / "20260929_103052_张三_1234.eml"
        parsed = email.message_from_bytes(eml_path.read_bytes(), policy=email.policy.default)
        self.assertEqual(list(parsed.iter_attachments()), [])
        self.assertIn("超过邮件附件上限", parsed.get_body(preferencelist=("plain",)).get_content())


if __name__ == "__main__":
    unittest.main()
