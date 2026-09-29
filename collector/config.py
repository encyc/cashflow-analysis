"""集中读取 collector 配置：环境变量优先，其次 collector/.env 文件。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def _get(env_file: dict[str, str], key: str, default: str) -> str:
    value = os.environ.get(key)
    if value is None or value == "":
        value = env_file.get(key, default)
    return value


def _get_bool(env_file: dict[str, str], key: str, default: str) -> bool:
    return _get(env_file, key, default).lower() in ("1", "true", "yes", "on")


@dataclass
class Config:
    port: int = 8000
    inbox_dir: Path = BASE_DIR / "inbox"
    outbox_dir: Path = BASE_DIR / "outbox"
    max_upload_mb: int = 100
    mail_attach_limit_mb: int = 45
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_ssl: bool = True
    smtp_user: str = ""
    smtp_pass: str = ""
    mail_from: str = ""
    mail_to: str = ""
    rate_limit_per_ip: int = 5
    rate_limit_window_min: int = 10

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def attach_limit_bytes(self) -> int:
        return self.mail_attach_limit_mb * 1024 * 1024

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.mail_to)


def load_config(env_path: Path | None = None) -> Config:
    env_file = _load_env_file(env_path or BASE_DIR / ".env")
    return Config(
        port=int(_get(env_file, "PORT", "8000")),
        inbox_dir=BASE_DIR / _get(env_file, "INBOX_DIR", "inbox"),
        outbox_dir=BASE_DIR / _get(env_file, "OUTBOX_DIR", "outbox"),
        max_upload_mb=int(_get(env_file, "MAX_UPLOAD_MB", "100")),
        mail_attach_limit_mb=int(_get(env_file, "MAIL_ATTACH_LIMIT_MB", "45")),
        smtp_host=_get(env_file, "SMTP_HOST", ""),
        smtp_port=int(_get(env_file, "SMTP_PORT", "465")),
        smtp_ssl=_get_bool(env_file, "SMTP_SSL", "true"),
        smtp_user=_get(env_file, "SMTP_USER", ""),
        smtp_pass=_get(env_file, "SMTP_PASS", ""),
        mail_from=_get(env_file, "MAIL_FROM", ""),
        mail_to=_get(env_file, "MAIL_TO", ""),
        rate_limit_per_ip=int(_get(env_file, "RATE_LIMIT_PER_IP", "5")),
        rate_limit_window_min=int(_get(env_file, "RATE_LIMIT_WINDOW_MIN", "10")),
    )
