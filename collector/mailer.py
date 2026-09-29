"""构建并发送提交通知邮件；SMTP 未配置时 dry-run 生成 .eml 到 outbox/。"""

from __future__ import annotations

import smtplib
import time
from email.message import EmailMessage
from pathlib import Path

from config import Config

PLATFORM_LABELS = {"wechat": "微信", "alipay": "支付宝"}
_ATTACHMENT_TYPES = {
    ".zip": "application/zip",
    ".pdf": "application/pdf",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
_RETRY_TIMES = 3


def _size_text(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.1f} MB"
    return f"{size / 1024:.1f} KB"


def build_message(config: Config, meta: dict, file_path: Path | None) -> EmailMessage:
    platform = PLATFORM_LABELS.get(meta["platform"], meta["platform"])
    received = meta["received_at"]
    msg = EmailMessage()
    msg["Subject"] = (
        f"【流水采集】{meta['name']}-{platform}-"
        f"{received[5:10].replace('-', '')} {received[11:16]}"
    )
    msg["From"] = config.mail_from or config.smtp_user
    msg["To"] = config.mail_to
    lines = [
        "收到新的客户流水提交：",
        "",
        f"客户姓名：{meta['name']}",
        f"手机号码：{meta['phone']}",
        f"业务单号：{meta['order_no'] or '（未填写）'}",
        f"流水平台：{platform}",
        f"解压密码：{meta['password']}",
        f"文件名称：{meta['original_filename']}",
        f"文件大小：{_size_text(meta['file_size'])}",
        f"文件SHA256：{meta['sha256']}",
        f"留档路径：{meta['submission_id']}",
        f"提交时间：{received}",
    ]
    if file_path is None:
        lines += ["", "提示：文件超过邮件附件上限，未随邮件附上，请在服务器留档路径获取。"]
    msg.set_content("\n".join(lines))
    if file_path is not None:
        data = file_path.read_bytes()
        maintype, _, subtype = _ATTACHMENT_TYPES.get(
            file_path.suffix.lower(), "application/octet-stream"
        ).partition("/")
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=file_path.name)
    return msg


def send_submission_mail(config: Config, meta: dict, file_path: Path) -> str:
    """发送邮件并返回 mail_status：dry-run / sent / failed: 原因。"""
    attach = file_path if file_path.stat().st_size <= config.attach_limit_bytes else None
    msg = build_message(config, meta, attach)

    if not config.smtp_configured:
        config.outbox_dir.mkdir(parents=True, exist_ok=True)
        # submission_id 全局唯一（同秒重名有 _2 序号），用作 .eml 文件名避免覆盖
        eml_name = meta["submission_id"].replace("/", "_")
        eml_path = config.outbox_dir / f"{eml_name}.eml"
        with eml_path.open("wb") as fp:
            fp.write(bytes(msg))
        return "dry-run"

    last_error: Exception | None = None
    for _ in range(_RETRY_TIMES):
        try:
            if config.smtp_ssl:
                server = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=30)
            else:
                server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30)
                server.starttls()
            with server:
                if config.smtp_user:
                    server.login(config.smtp_user, config.smtp_pass)
                server.send_message(msg)
            return "sent"
        except Exception as exc:  # 记录原因并重试，最终原因写入 meta.mail_status
            last_error = exc
            time.sleep(2)
    return f"failed: {last_error}"
