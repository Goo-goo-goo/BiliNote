"""B 站二维码登录。

复用 B 站网页端官方的扫码登录端点（passport.bilibili.com），用户用手机
B 站 App 扫码确认后，登录凭据以 Set-Cookie 形式下发。我们提取其中的
SESSDATA / bili_jct / DedeUserID 拼成 yt-dlp 可用的 Cookie 串，
存入 CookieConfigManager（platform="bilibili"），之后下载就走登录态。

流程：
  1. GET  /api/bili_qrcode          → 生成二维码，返回 qrcode_key + PNG(base64)
  2. GET  /api/bili_qrcode/status   → 轮询扫码结果；成功时自动保存 cookie
"""
import base64
import io
from typing import Dict, Optional

import requests

from app.services.cookie_manager import CookieConfigManager

GENERATE_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
# 注意：旧的 /web/login/info 端点已下线（404），轮询必须用 /web/qrcode/poll
POLL_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
HOME_URL = "https://www.bilibili.com"

# 登录成功后写入 cookie 串的字段（按 yt-dlp 访问 B 站接口的必要程度排序）
COOKIE_KEYS = ["SESSDATA", "bili_jct", "DedeUserID", "DedeUserID__ckMd5", "sid"]

# 轮询返回 data.code 的语义（B 站自定义码，不是 HTTP 状态码）
CODE_SCANNED_CONFIRMED = 0      # 扫码并确认，登录成功
CODE_NOT_SCANNED = 86101        # 未扫码
CODE_SCANNED_NOT_CONFIRMED = 86090  # 已扫码，未在手机上确认
CODE_QR_EXPIRED = 86038         # 二维码已失效，需重新生成


def _new_session() -> requests.Session:
    """passport 接口要求携带匿名 cookie（buvid3 等），先访问主站拿一套。"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Referer": "https://www.bilibili.com/",
    })
    session.get(HOME_URL, timeout=10)
    return session


def generate_qrcode() -> Dict[str, str]:
    """申请登录二维码，返回二维码图片(base64 PNG)和轮询用的 qrcode_key。"""
    import qrcode

    session = _new_session()
    resp = session.get(GENERATE_URL, params={"source": "main-fe-header"}, timeout=10)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("code") != 0:
        raise RuntimeError(f"申请二维码失败: {payload.get('message') or payload}")

    login_url = payload["data"]["url"]
    qrcode_key = payload["data"]["qrcode_key"]

    img = qrcode.make(login_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    return {"qrcode_key": qrcode_key, "qr_png_base64": qr_b64, "login_url": login_url}


def poll_qrcode(qrcode_key: str) -> Dict[str, Optional[str]]:
    """轮询扫码状态。成功时保存 cookie 并返回之。

    返回 {status, cookie}，status ∈ pending / scanned / expired / success。
    仅 status == "success" 时 cookie 非空。
    """
    session = _new_session()
    resp = session.get(POLL_URL, params={"qrcode_key": qrcode_key}, timeout=10)
    resp.raise_for_status()
    payload = resp.json()
    data = payload.get("data") or {}
    code = data.get("code")

    if code == CODE_QR_EXPIRED:
        return {"status": "expired", "cookie": None}
    if code == CODE_NOT_SCANNED:
        return {"status": "pending", "cookie": None}
    if code == CODE_SCANNED_NOT_CONFIRMED:
        return {"status": "scanned", "cookie": None}
    if code != CODE_SCANNED_CONFIRMED:
        raise RuntimeError(f"查询扫码状态失败: {payload.get('message') or payload}")

    # 成功：SESSDATA 等在响应的 Set-Cookie 里
    jar = session.cookies
    pairs = [f"{k}={jar.get(k)}" for k in COOKIE_KEYS if jar.get(k)]
    if not pairs:
        raise RuntimeError("扫码成功但未获取到登录凭据（SESSDATA），请重试")
    cookie = "; ".join(pairs)

    CookieConfigManager().set("bilibili", cookie)
    return {"status": "success", "cookie": cookie}
