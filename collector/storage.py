"""提交落盘：inbox/YYYYMMDD/HHMMSS_姓名_手机尾号/ 内保存原始文件与 meta.json。"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_MAX_STEM_LEN = 120


def sanitize_component(text: str, max_len: int = 30) -> str:
    """清洗用于目录名/文件名的短文本（姓名等），去掉路径与控制字符。"""
    text = _CONTROL_CHARS.sub("", text).replace("/", "").replace("\\", "").strip()
    return text[:max_len] or "未知"


def sanitize_filename(filename: str, fallback: str = "unnamed") -> str:
    """保留客户原始文件名，仅去除路径穿越与控制字符，超长截断主干保留扩展名。"""
    name = filename.replace("\\", "/").split("/")[-1]
    name = _CONTROL_CHARS.sub("", name).strip().lstrip(".")
    if not name:
        return fallback
    if "." in name:
        stem, _, ext = name.rpartition(".")
        ext = ext[:16]
    else:
        stem, ext = name, ""
    stem = stem[:_MAX_STEM_LEN] or fallback
    return f"{stem}.{ext}" if ext else stem


def _unique_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    if "." in filename:
        stem, _, ext = filename.rpartition(".")
        template = "{stem}_{i}.{ext}"
    else:
        stem, ext = filename, ""
        template = "{stem}_{i}"
    i = 2
    while True:
        candidate = directory / template.format(stem=stem, i=i, ext=ext)
        if not candidate.exists():
            return candidate
        i += 1


def save_submission(
    inbox_dir: Path,
    *,
    filename: str,
    data: bytes,
    platform: str,
    name: str,
    phone: str,
    order_no: str,
    password: str,
    ip_hash: str,
    now: datetime | None = None,
) -> tuple[str, dict, Path, Path]:
    """写入留档目录，返回 (submission_id, meta, 文件路径, meta 路径)。"""
    now = now or datetime.now()
    day_dir = inbox_dir / now.strftime("%Y%m%d")
    base = f"{now.strftime('%H%M%S')}_{sanitize_component(name)}_{phone[-4:]}"
    submission_dir = day_dir / base
    i = 2
    while submission_dir.exists():
        submission_dir = day_dir / f"{base}_{i}"
        i += 1
    submission_dir.mkdir(parents=True)

    file_path = _unique_path(submission_dir, sanitize_filename(filename))
    file_path.write_bytes(data)

    meta = {
        "submission_id": submission_dir.relative_to(inbox_dir).as_posix(),
        "platform": platform,
        "name": name,
        "phone": phone,
        "order_no": order_no,
        "password": password,
        "original_filename": filename,
        "stored_filename": file_path.name,
        "file_size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "received_at": now.isoformat(timespec="seconds"),
        "ip_hash": ip_hash,
        "mail_status": "pending",
    }
    meta_path = submission_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta["submission_id"], meta, file_path, meta_path


def update_mail_status(meta_path: Path, status: str) -> None:
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["mail_status"] = status
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
