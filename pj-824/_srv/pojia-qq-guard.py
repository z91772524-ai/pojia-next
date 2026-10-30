#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""破甲 QQ 机器人守护台（pojia-qq-guard）

背景：QQ 会话被踢（KickedOffLine "登录已失效"）后，NapCat 的快速登录 token 被判废，
只能出二维码等人工扫 —— 这时候机器人在群里彻底哑掉，人不在电脑前就没人救。

本服务把「在线状态 + 当前二维码」做成一个带密钥的网页：
手机点开 → 扫码 → 30 秒内恢复，不用 SSH、不用进 docker、不用开电脑。

  /qr/<SECRET>/         状态 + 二维码（5 秒自动刷新）
  /qr/<SECRET>/qr.png   只取二维码图片（带 no-store）
  /qr/<SECRET>/status   JSON
  /qr/<SECRET>/restart  手动重启 napcat 容器（GET 也行，方便手机点）

watchdog 每 5 秒探一次 onebot 的 get_login_info：
  · 在线：记录上线时间
  · 离线：抓容器里的 qrcode.png 到本地缓存；若二维码连续 6 分钟没更新
          （说明 worker 卡死不再重试），自动 docker restart napcat（10 分钟冷却）
掉线 / 恢复都会记进事件表，页面上能直接看到「这次掉了多久」。
"""
import json
import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen

try:
    os.environ["TZ"] = "Asia/Shanghai"
    time.tzset()
except Exception:
    pass

SECRET = os.environ.get("QQ_GUARD_SECRET", "CHANGE_ME_SECRET")
PORT = int(os.environ.get("QQ_GUARD_PORT", "3110"))
CONTAINER = "napcat"
API = "http://127.0.0.1:3000"
TOKEN = os.environ.get("QQ_GUARD_TOKEN", "pojia-napcat-9x4k")
QR_IN_CONTAINER = "/app/napcat/cache/qrcode.png"
QR_CACHE = "/var/www/qr-cache/qrcode.png"

CHECK_INTERVAL = 5          # 秒
QR_STALE_RESTART = 900      # 离线且二维码 15 分钟没更新 → 重启容器（NapCat 每 2 分钟刷一次码）
RESTART_COOLDOWN = 600      # 两次自动重启最小间隔

STATE = {
    "online": None,          # None=还没探过
    "online_since": 0,       # 本次上线时间
    "offline_since": 0,      # 本次掉线时间
    "qr_mtime": 0,           # 二维码文件最后更新时间
    "qr_sig": 0,
    "restarts": 0,
    "last_restart": 0,
    "checked": 0,
    "events": [],            # [{ts, kind, note}]
}
LOCK = threading.Lock()


def now():
    return int(time.time())


def fmt(ts):
    if not ts:
        return "-"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def event(kind, note=""):
    with LOCK:
        STATE["events"].append({"ts": now(), "kind": kind, "note": note})
        STATE["events"] = STATE["events"][-60:]
    print("[%s] %s %s" % (fmt(now()), kind, note), flush=True)


def napcat_online():
    """调 onebot HTTP get_login_info。

    返回 (status, uid, note)：status=True 在线 / False 明确离线 / None 探不到（网络异常，
    此时绝不当成掉线处理，避免误重启）。
    """
    try:
        req = Request(API + "/get_login_info", data=b"{}", method="POST",
                      headers={"Authorization": "Bearer " + TOKEN,
                               "Content-Type": "application/json"})
        with urlopen(req, timeout=4) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        return None, "", "%s" % type(e).__name__          # 探不到 ≠ 掉线
    if d.get("status") in ("ok", "async") or d.get("retcode") == 0:
        info = d.get("data") or {}
        if info.get("user_id"):
            return True, str(info.get("user_id")), str(info.get("nickname") or "")
        return False, "", "已连接但未登录"
    return False, "", str(d.get("message") or d.get("wording") or "未登录")


def fetch_qr():
    """把容器里的二维码抓到本地缓存，返回是否更新。"""
    try:
        os.makedirs(os.path.dirname(QR_CACHE), exist_ok=True)
        tmp = QR_CACHE + ".tmp"
        p = subprocess.run(["docker", "cp", CONTAINER + ":" + QR_IN_CONTAINER, tmp],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        if p.returncode != 0 or not os.path.exists(tmp):
            return False
        st = os.stat(tmp)
        if st.st_size < 200:                     # 太小的是坏图
            os.unlink(tmp)
            return False
        with LOCK:
            if st.st_mtime_ns == STATE["qr_sig"]:
                os.unlink(tmp)
                return False
            STATE["qr_sig"] = st.st_mtime_ns
            STATE["qr_mtime"] = int(st.st_mtime)
        os.replace(tmp, QR_CACHE)
        return True
    except Exception as e:
        print("fetch_qr error: %r" % (e,), flush=True)
        return False


def restart_container(reason):
    with LOCK:
        if now() - STATE["last_restart"] < RESTART_COOLDOWN:
            return False
        STATE["last_restart"] = now()
        STATE["restarts"] += 1
    event("restart", reason)
    try:
        subprocess.run(["docker", "restart", CONTAINER], timeout=90,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(8)
        return True
    except Exception as e:
        event("restart_fail", "%r" % (e,))
        return False


def loop():
    miss = 0                      # 连续「探不到」次数，别把网络抖动当掉线
    while True:
        try:
            ok, uid, extra = napcat_online()
            if ok is None:
                miss += 1
                if miss == 1 or miss % 60 == 0:
                    print("probe failed (%d): %s" % (miss, extra), flush=True)
                time.sleep(CHECK_INTERVAL)
                continue
            miss = 0
            with LOCK:
                prev = STATE["online"]
                STATE["checked"] = now()
                STATE["online"] = ok
                if ok:
                    STATE["offline_since"] = 0
                    if prev is not True or not STATE["online_since"]:
                        STATE["online_since"] = now()
                else:
                    STATE["online_since"] = 0
                    if not STATE["offline_since"]:
                        STATE["offline_since"] = now()
            if prev is not ok:
                if ok:
                    down = 0
                    with LOCK:
                        ev = [e for e in STATE["events"] if e["kind"] == "offline"]
                        if ev:
                            down = now() - ev[-1]["ts"]
                    event("online", "恢复(QQ %s %s) 掉线 %d 分" % (uid, extra, down // 60))
                else:
                    event("offline", "探测: %s" % (extra or "未登录",))
            if not ok:
                fetch_qr()
                with LOCK:
                    qr_age = now() - STATE["qr_mtime"] if STATE["qr_mtime"] else 0
                # 只有「明确离线」且二维码长时间不再刷新（worker 不再重试）才动容器
                if STATE["qr_mtime"] and qr_age > QR_STALE_RESTART:
                    restart_container("二维码 %d 分钟未更新，疑似 worker 卡死" % (qr_age // 60))
        except Exception as e:
            print("loop error: %r" % (e,), flush=True)
        time.sleep(CHECK_INTERVAL)


CSS = """
:root{--ac:#0d9488;--ok:#16a34a;--bad:#e0593f;--tx:#21302e;--dim:#6b7c79;--line:#dfeae7}
*{box-sizing:border-box;margin:0;padding:0}
body{font:15px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;color:var(--tx);
background:#eef2f1;padding:16px;max-width:520px;margin:0 auto}
.card{background:#fff;border:1px solid var(--line);border-radius:16px;padding:18px;margin-bottom:14px;
box-shadow:0 6px 24px -18px rgba(6,35,29,.4)}
h1{font-size:16px;margin-bottom:4px}
.st{font-size:26px;font-weight:800;margin:6px 0 2px}
.on{color:var(--ok)} .off{color:var(--bad)} .unk{color:var(--dim)}
.sub{color:var(--dim);font-size:12.5px}
img{width:100%;max-width:340px;display:block;margin:12px auto;border-radius:10px;border:1px solid var(--line)}
.btn{display:inline-block;padding:10px 16px;border-radius:10px;background:var(--ac);color:#fff;
text-decoration:none;font-weight:700;font-size:14px;margin-top:8px}
table{width:100%;border-collapse:collapse;font-size:12.5px}
td{padding:6px 4px;border-bottom:1px solid #f0f5f4;vertical-align:top}
td.t{color:var(--dim);white-space:nowrap;width:96px}
.tag{padding:1px 6px;border-radius:5px;font-size:11px;font-weight:700}
.tag.offline{background:#fdecea;color:var(--bad)} .tag.online{background:#e8f6ec;color:var(--ok)}
.tag.restart{background:#fff4e5;color:#b87503}
.tip{color:var(--dim);font-size:12px;margin-top:10px;line-height:1.5}
"""


def page():
    with LOCK:
        st = dict(STATE)
        evs = list(STATE["events"])
    if st["online"] is True:
        cls, txt, extra = "on", "在线", "自 " + fmt(st["online_since"])
    elif st["online"] is False:
        cls, txt = "off", "离线"
        extra = "自 " + fmt(st["offline_since"]) + ("（已 %d 分钟）" % ((now() - st["offline_since"]) // 60)
                                                    if st["offline_since"] else "")
    else:
        cls, txt, extra = "unk", "探测中…", ""
    qr_block = ""
    if st["online"] is False:
        qr_block = ('<img src="qr.png?t=%d" alt="登录二维码">'
                    '<div class="sub">二维码更新于 %s</div>'
                    '<a class="btn" href="restart" onclick="return confirm(\'重启 napcat？约 30 秒\')">重启 QQ 容器</a>'
                    % (st["qr_mtime"], fmt(st["qr_mtime"])))
    rows = []
    for e in reversed(evs[-14:]):
        tag = {"offline": "掉线", "online": "恢复", "restart": "重启", "restart_fail": "重启失败"}.get(e["kind"], e["kind"])
        rows.append('<tr><td class="t">%s</td><td><span class="tag %s">%s</span> %s</td></tr>'
                    % (fmt(e["ts"]), e["kind"], tag, e["note"]))
    return ("<!DOCTYPE html><html lang=zh-CN><head><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            "<meta http-equiv=refresh content=5><title>大肥鱼 · 守护台</title>"
            "<style>%s</style></head><body>"
            "<div class=card><h1>大肥鱼 · QQ 机器人守护台</h1>"
            "<div class='st %s'>%s</div><div class=sub>%s</div>"
            "<div class=sub style='margin-top:6px'>最后探测 %s · 自动重启 %d 次</div>"
            "%s</div>"
            "<div class=card><h1>最近事件</h1><table>%s</table>"
            "<div class=tip>QQ 被判「登录已失效」时（在手机/电脑上重登同一个号就会这样），"
            "用手机 QQ 扫上面的二维码授权即可恢复，约 30 秒。扫完请在手机上把该号退出登录，"
            "别让它长期挂着，否则下次重登还会把它踢掉。</div></div>"
            "</body></html>") % (CSS, cls, txt, extra, fmt(st["checked"]), st["restarts"],
                                 qr_block, "".join(rows) or "<tr><td class=sub>暂无</td></tr>")


class H(BaseHTTPRequestHandler):
    server_version = "qq-guard/1.0"

    def _ok(self, body, ctype="text/html; charset=utf-8", code=200, extra=None):
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")
        pre = "/qr/" + SECRET
        if not (path == pre or path.startswith(pre + "/")):
            return self._ok("not found", code=404)
        sub = path[len(pre):]
        if sub in ("", "/"):
            return self._ok(page())
        if sub == "/qr.png":
            try:
                with open(QR_CACHE, "rb") as f:
                    return self._ok(f.read(), ctype="image/png")
            except OSError:
                return self._ok(b"", ctype="image/png", code=404)
        if sub == "/status":
            with LOCK:
                return self._ok(json.dumps(dict(STATE), ensure_ascii=False, default=str),
                                ctype="application/json; charset=utf-8")
        if sub == "/restart":
            restart_container("手动重启")
            return self._ok("<!DOCTYPE html><meta charset=utf-8><body style='font:15px sans-serif;padding:24px'>"
                            "已请求重启，15 秒后再看。<a href='./'>返回</a></body>")
        return self._ok("not found", code=404)

    def log_message(self, *a):
        pass


def main():
    os.makedirs(os.path.dirname(QR_CACHE), exist_ok=True)
    threading.Thread(target=loop, name="watch", daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print("qq-guard listening 127.0.0.1:%d  secret=%s..." % (PORT, SECRET[:6]), flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
