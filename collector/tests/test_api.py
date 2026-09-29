import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # collector/

from fastapi.testclient import TestClient

from config import Config
from server import create_app


def make_zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("demo.csv", "时间,金额\n2026-09-29,100.00\n")
    return buf.getvalue()


def make_client(tmp: Path, max_upload_mb: int = 100, rate_limit: int = 5) -> TestClient:
    cfg = Config(
        inbox_dir=tmp / "inbox",
        outbox_dir=tmp / "outbox",
        max_upload_mb=max_upload_mb,
        rate_limit_per_ip=rate_limit,
    )
    return TestClient(create_app(cfg))


def valid_payload(**overrides) -> dict:
    payload = {
        "files": {"file": ("微信证明.zip", make_zip_bytes(), "application/zip")},
        "data": {
            "platform": "wechat",
            "password": "abc123",
            "name": "张三",
            "phone": "13800001234",
            "order_no": "A-001",
        },
    }
    payload.update(overrides)
    return payload


class StaticTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.client = make_client(self.tmp)

    def test_index_served(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("流水资料提交", resp.text)

    def test_inbox_not_exposed(self):
        (self.tmp / "inbox" / "20260929").mkdir(parents=True)
        (self.tmp / "inbox" / "20260929" / "secret.txt").write_text("x")
        self.assertEqual(self.client.get("/inbox/20260929/secret.txt").status_code, 404)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.client = make_client(self.tmp)

    def post(self, payload):
        return self.client.post("/api/submissions", **payload)

    def assert_error(self, resp, status):
        self.assertEqual(resp.status_code, status)
        body = resp.json()
        self.assertFalse(body["ok"])
        self.assertTrue(body["error"])

    def test_missing_file(self):
        self.assert_error(self.post({"data": {"platform": "wechat", "password": "p1", "name": "张三", "phone": "13800001234"}}), 422)

    def test_bad_extension(self):
        payload = valid_payload()
        payload["files"] = {"file": ("photo.jpg", b"xxxx", "image/jpeg")}
        self.assert_error(self.post(payload), 422)

    def test_bad_phone(self):
        payload = valid_payload()
        payload["data"] = dict(payload["data"], phone="12345")
        self.assert_error(self.post(payload), 422)

    def test_bad_platform(self):
        payload = valid_payload()
        payload["data"] = dict(payload["data"], platform="bank")
        self.assert_error(self.post(payload), 422)

    def test_short_name(self):
        payload = valid_payload()
        payload["data"] = dict(payload["data"], name="张")
        self.assert_error(self.post(payload), 422)

    def test_empty_password(self):
        payload = valid_payload()
        payload["data"] = dict(payload["data"], password="")
        self.assert_error(self.post(payload), 422)

    def test_oversize(self):
        client = make_client(self.tmp, max_upload_mb=1)
        big = b"x" * (1024 * 1024 + 100)
        resp = client.post(
            "/api/submissions",
            files={"file": ("big.zip", big, "application/zip")},
            data={"platform": "wechat", "password": "p1", "name": "张三", "phone": "13800001234"},
        )
        self.assert_error(resp, 422)


class SubmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.client = make_client(self.tmp)

    def test_valid_submission_lands_in_inbox_and_outbox(self):
        zip_bytes = make_zip_bytes()
        resp = self.client.post(
            "/api/submissions",
            files={"file": ("微信证明.zip", zip_bytes, "application/zip")},
            data={"platform": "wechat", "password": "abc123", "name": "张三",
                  "phone": "13800001234", "order_no": "A-001"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["submission_id"])

        submission_dir = self.tmp / "inbox" / body["submission_id"]
        saved_file = submission_dir / "微信证明.zip"
        self.assertEqual(saved_file.read_bytes(), zip_bytes)
        meta = json.loads((submission_dir / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["password"], "abc123")
        self.assertEqual(meta["phone"], "13800001234")
        self.assertEqual(meta["mail_status"], "dry-run")

        eml_files = list((self.tmp / "outbox").glob("*.eml"))
        self.assertEqual(len(eml_files), 1)

    def test_rate_limit(self):
        client = make_client(self.tmp, rate_limit=2)
        for _ in range(2):
            resp = client.post("/api/submissions", **valid_payload())
            self.assertEqual(resp.status_code, 200)
        third = client.post("/api/submissions", **valid_payload())
        self.assertEqual(third.status_code, 429)
        self.assertFalse(third.json()["ok"])


if __name__ == "__main__":
    unittest.main()
