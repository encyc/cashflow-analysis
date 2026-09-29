"""FastAPI 服务：托管 H5 静态页 + POST /api/submissions 接收流水文件。"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

try:  # 兼容 `python collector/server.py` 与 `uvicorn collector.server:app` 两种启动方式
    from .config import Config, load_config
    from .mailer import send_submission_mail
    from .storage import save_submission, update_mail_status
except ImportError:
    from config import Config, load_config
    from mailer import send_submission_mail
    from storage import save_submission, update_mail_status

logger = logging.getLogger("collector")

WEB_DIR = Path(__file__).resolve().parent / "web"
ALLOWED_EXTENSIONS = {".zip", ".pdf", ".xlsx", ".xls"}
PHONE_RE = re.compile(r"^1\d{10}$")
PLATFORMS = {"wechat", "alipay"}


def mask_phone(phone: str) -> str:
    return f"{phone[:3]}****{phone[-4:]}" if len(phone) == 11 else phone


def mask_password(password: str) -> str:
    return (password[:2] + "***") if password else "***"


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimiter:
    """内存级每 IP 滑动窗口限流，进程重启即清零。"""

    def __init__(self, limit: int, window_min: int):
        self.limit = limit
        self.window = window_min * 60
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        if self.limit <= 0:
            return True
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True


def _validate(form, allowed_extensions) -> str | None:
    file = form.get("file")
    if file is None or not getattr(file, "filename", ""):
        return "请选择要上传的流水文件"
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        return "仅支持 zip / pdf / xlsx / xls 格式的流水文件"
    if form.get("platform") not in PLATFORMS:
        return "请选择流水平台"
    password = form.get("password")
    if not isinstance(password, str) or not (1 <= len(password) <= 64):
        return "请填写文件解压密码（1-64 个字符）"
    name = (form.get("name") or "").strip()
    if not (2 <= len(name) <= 30):
        return "请填写客户姓名（2-30 个字符）"
    phone = (form.get("phone") or "").strip()
    if not PHONE_RE.match(phone):
        return "请填写正确的 11 位手机号"
    order_no = (form.get("order_no") or "").strip()
    if len(order_no) > 32:
        return "业务单号过长（最多 32 个字符）"
    return None


def create_app(config: Config | None = None) -> FastAPI:
    config = config or load_config()
    app = FastAPI(title="collector", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.config = config
    app.state.rate_limiter = RateLimiter(config.rate_limit_per_ip, config.rate_limit_window_min)

    @app.post("/api/submissions")
    async def submit(request: Request) -> JSONResponse:
        cfg = request.app.state.config
        ip_hash = hashlib.sha256(client_ip(request).encode()).hexdigest()[:8]
        if not request.app.state.rate_limiter.allow(ip_hash):
            return JSONResponse({"ok": False, "error": "提交过于频繁，请稍后再试"}, status_code=429)

        form = await request.form()
        error = _validate(form, ALLOWED_EXTENSIONS)
        if error:
            return JSONResponse({"ok": False, "error": error}, status_code=422)

        upload = form["file"]
        data = await upload.read()
        await upload.close()
        if len(data) > cfg.max_upload_bytes:
            return JSONResponse(
                {"ok": False, "error": f"文件超过大小上限（{cfg.max_upload_mb}MB）"}, status_code=422
            )

        # 密码不做 strip：解压密码可能合法地包含首尾空格以外的特殊字符，按原文保存
        submission_id, meta, file_path, meta_path = save_submission(
            cfg.inbox_dir,
            filename=upload.filename or "unnamed",
            data=data,
            platform=form["platform"],
            name=form["name"].strip(),
            phone=form["phone"].strip(),
            order_no=(form.get("order_no") or "").strip(),
            password=form["password"],
            ip_hash=ip_hash,
        )
        mail_status = send_submission_mail(cfg, meta, file_path)
        update_mail_status(meta_path, mail_status)
        logger.info(
            "submission=%s name=%s phone=%s platform=%s size=%d mail=%s pwd=%s",
            submission_id, meta["name"], mask_phone(meta["phone"]), meta["platform"],
            meta["file_size"], mail_status, mask_password(meta["password"]),
        )
        return JSONResponse({"ok": True, "submission_id": submission_id})

    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    uvicorn.run(app, host="0.0.0.0", port=load_config().port)
