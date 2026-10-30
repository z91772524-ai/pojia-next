#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pojia-admin —— 破甲一键通统一后台（替代 qq-bridge 控制台 + pojia 原管理后台）

设计要点
--------
1) 一个入口、一套密码。旧的两套后台（qq-bridge 的 console.html、pojia-cloud 的
   admin.html）都是「一个页面塞几十个面板 + 各自一套令牌」，手机上根本用不了。
   这里只做一件事：一个入口，左边选功能，右边出结果，全部面板懒加载。
2) 不重写业务，只做编排。真正的写操作仍然落到原服务：
     · /adm/api/qq/*    → qq-bridge console（服务端注入 x-console-token，
                          浏览器永远看不到那个令牌）
     · /adm/api/cloud/* → 127.0.0.1:443 的 /api/admin/*（服务端用 web_admin
                          账号登录拿会话令牌，过期自动重登一次）
   这样旧后台有的功能一个都不会丢。
3) 新增的运维面：健康检查、日志尾巴、备份/回滚、通知测试、审计、跨表搜索。

路由
----
  GET  /adm                         页面
  GET  /adm/api/me                  会话状态
  POST /adm/api/login   {p}         登录
  POST /adm/api/logout
  *    /adm/api/qq/<path>           console 反向代理
  POST /adm/api/cloud/<name>        pojia admin 反代（body 里自动补 token）
  GET  /adm/api/cloudimg?ep=&id=    单张广告图（列表里不塞 base64）
  GET  /adm/api/sys/health
  GET  /adm/api/sys/logs?unit=&n=
  GET  /adm/api/sys/dlog?n=
  GET  /adm/api/sys/backups
  POST /adm/api/sys/backup {note}
  POST /adm/api/sys/restore {name}
  POST /adm/api/sys/restart {unit}
  POST /adm/api/sys/notify {ch}
  GET  /adm/api/sys/audit?n=
  GET  /adm/api/sys/search?q=
  GET  /adm/api/napcat/status
  GET  /adm/api/napcat/qr.png
  POST /adm/api/napcat/restart
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import socket
import sqlite3
import ssl
import subprocess
import sys
import tarfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, quote
from urllib.request import Request, urlopen

ROOT = os.environ.get("PA_ROOT", "/opt/pojia-admin")
PORT = int(os.environ.get("PA_PORT", "3120"))
BIND = os.environ.get("PA_BIND", "127.0.0.1")

SECRET_F = os.path.join(ROOT, "secret")
AUTH_F = os.path.join(ROOT, "auth.json")
AUDIT_F = os.path.join(ROOT, "audit.jsonl")
WATCH_F = os.path.join(ROOT, "watch.jsonl")
HEAL_F = os.path.join(ROOT, "autoheal.json")
BAK_DIR = os.path.join(ROOT, "backups")
HTML_F = os.path.join(ROOT, "admin.html")

CLOUD_CFG = "/opt/pojia-cloud/config.json"
CLOUD_TK_F = os.path.join(ROOT, "cloud_token.json")
CLOUD_BASE = "https://127.0.0.1"
QQ_BASE = "http://127.0.0.1:3100"
QQ_TOKEN_F = "/opt/qq-bridge/state/console-token"
GUARD_BASE = "http://127.0.0.1:3110"
GUARD_UNIT = "/etc/systemd/system/pojia-qq-guard.service"
DB_F = "/opt/pojia-cloud/data/pojia.db"

SESSION_TTL = 12 * 3600
COOKIE = "pa"
LOGIN_MAX_FAIL = 6
LOGIN_LOCK = 900

# 允许被代理的 admin 端点（白名单，避免变成任意 SSRF）
CLOUD_ALLOW = {
    "login", "login-sessions", "login-sessions-del", "trust-login", "trust-register",
    "dashboard", "data", "msg", "board", "ads", "guiads", "version", "dlurl", "notice",
    "groups", "group-refresh", "system", "config", "words", "pirate", "donate", "paycfg",
    "income", "balance", "unlim-list", "unlim-set", "settings", "vote", "ad-report",
    "unbind-orders", "unbind-approve", "battle", "db", "action", "batch", "extra",
    "userlog", "napcat-url",
}

SERVICES = [
    ("pojia-cloud", "客户端分发核心（443/8443）"),
    ("pojia-code-web", "领码站 /codeweb"),
    ("pojia-site", "官网 + 留言板"),
    ("pojia-card", "发卡领卡站"),
    ("qq-bridge", "QQ 机器人（大肥鱼 / DSH 桥）"),
    ("pojia-qq-easteregg", "QQ 群聊应答（备用线路）"),
    ("pojia-qq-guard", "QQ 掉线守卫台"),
    ("napcat-guard", "群防炸群 / 敏感词"),
    ("pojia-qqbot", "QQ 官方机器人校验"),
    ("nginx", "反向代理"),
    ("dsh", "DSH 运行时（127.0.0.1:3080）"),
]

PORTS = [(443, "https 主站"), (8443, "老版本兼容"), (8080, "领码站"), (8088, "发卡站"),
         (8090, "官网"), (80, "nginx"), (3000, "NapCat onebot"), (3100, "qq-bridge 控制台"),
         (3110, "QQ 守卫台"), (3080, "DSH")]

_LOCK = threading.Lock()
_FAILS = {}          # ip -> [count, until]


# ---------------------------------------------------------------- 基础工具
def _read(path, default=""):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return default


def _read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {} if default is None else default


def _write_json(path, obj, mode=0o600):
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def secret():
    try:
        return open(SECRET_F, "rb").read()
    except Exception:
        data = secrets.token_bytes(32)
        fd = os.open(SECRET_F, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.write(fd, data)
        os.close(fd)
        return data


def auth_rec():
    rec = _read_json(AUTH_F)
    if not rec.get("hash"):
        salt = secrets.token_hex(16)
        rec = {"user": "admin", "salt": salt, "iter": 200000,
               "hash": _pw("36925814A", salt, 200000)}
        _write_json(AUTH_F, rec)
    return rec


def _pw(password, salt, iters):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                               salt.encode("utf-8"), iters).hex()


def audit(ip, act, detail=""):
    row = {"t": int(time.time()), "ip": ip, "act": act, "detail": str(detail)[:300]}
    try:
        with open(AUDIT_F, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def sh(cmd, timeout=20):
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, timeout=timeout)
        return (p.stdout or b"").decode("utf-8", "replace") + (p.stderr or b"").decode("utf-8", "replace")
    except Exception as exc:
        return "ERR %s: %s" % (type(exc).__name__, exc)


_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE


def http_json(url, body=None, headers=None, timeout=30, method=None, ctx=None):
    data = None
    hd = dict(headers or {})
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        hd["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=hd, method=method or ("POST" if data else "GET"))
    with urlopen(req, timeout=timeout, context=ctx) as r:
        raw = r.read()
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except Exception:
        return {"ok": 0, "err": "非 JSON 响应", "raw": raw[:200].decode("utf-8", "replace")}


# ---------------------------------------------------------------- 云端后台令牌
def _cloud_login():
    cfg = _read_json(CLOUD_CFG)
    wa = cfg.get("web_admin") or {}
    u, p = str(wa.get("user") or ""), str(wa.get("pass") or "")
    if not u or not p:
        raise RuntimeError("config.json 里没有 web_admin 账号")
    r = http_json(CLOUD_BASE + "/api/admin/login", {"u": u, "p": p}, ctx=_SSL, timeout=20)
    tk = r.get("token")
    if not tk:
        raise RuntimeError("原后台登录失败：%s" % (r.get("err") or r))
    _write_json(CLOUD_TK_F, {"token": tk, "ts": int(time.time())})
    return tk


def cloud_api(name, body):
    if name not in CLOUD_ALLOW:
        return {"ok": 0, "err": "不支持的接口：%s" % name}
    with _LOCK:
        rec = _read_json(CLOUD_TK_F)
        tk = rec.get("token") or ""
        if not tk or time.time() - float(rec.get("ts") or 0) > 6 * 3600:
            tk = _cloud_login()
    payload = dict(body or {})
    payload["token"] = tk
    r = http_json(CLOUD_BASE + "/api/admin/" + name, payload, ctx=_SSL, timeout=90)
    if isinstance(r, dict) and r.get("err") in ("expired", "bad token"):
        with _LOCK:
            tk = _cloud_login()
        payload["token"] = tk
        r = http_json(CLOUD_BASE + "/api/admin/" + name, payload, ctx=_SSL, timeout=90)
    return r


def qq_token():
    return _read(QQ_TOKEN_F).strip()


def qq_api(path, body=None, method=None):
    url = QQ_BASE + "/api/" + path.lstrip("/")
    return http_json(url, body, headers={"x-console-token": qq_token()},
                     timeout=60, method=method)


def guard_secret():
    txt = _read(GUARD_UNIT)
    m = re.search(r"QQ_GUARD_SECRET=(\S+)", txt)
    return m.group(1) if m else ""


# ---------------------------------------------------------------- 健康检查
def _port_open(port, host="127.0.0.1", t=0.4):
    s = socket.socket()
    s.settimeout(t)
    try:
        s.connect((host, port))
        return True
    except Exception:
        return False
    finally:
        s.close()


def health():
    out = {"ts": int(time.time()), "services": [], "ports": [], "sys": {}, "cert": {}, "disk": {}}
    for unit, label in SERVICES:
        st = sh("systemctl is-active %s" % unit).strip()
        out["services"].append({"unit": unit, "label": label, "state": st})
    for port, label in PORTS:
        out["ports"].append({"port": port, "label": label, "open": _port_open(port)})
    out["sys"]["host"] = socket.gethostname()
    out["sys"]["uptime"] = sh("cut -d. -f1 /proc/uptime").strip()
    out["sys"]["load"] = open("/proc/loadavg").read().split()[:3]
    try:
        mem = {}
        for line in open("/proc/meminfo"):
            k, v = line.split(":", 1)
            mem[k] = int(v.strip().split()[0])
        tot, avail = mem.get("MemTotal", 1), mem.get("MemAvailable", 0)
        out["sys"]["mem"] = {"total": tot // 1024, "avail": avail // 1024,
                             "pct": round(100.0 * (tot - avail) / tot, 1)}
    except Exception:
        pass
    line = sh("df -h / | tail -1").strip()
    out["disk"] = {"text": line}
    f = line.split()
    if len(f) >= 6:   # Filesystem Size Used Avail Use% Mounted
        out["disk"].update({"fs": f[0], "total": f[1], "used": f[2],
                            "avail": f[3], "pct": f[4], "mnt": f[5]})
    # 证书到期
    try:
        pem = sh("timeout 6 openssl s_client -servername pursueray.cn -connect 127.0.0.1:443 "
                 "2>/dev/null | openssl x509 -noout -enddate 2>/dev/null").strip()
        m = re.search(r"notAfter=(.+)", pem)
        if m:
            exp = m.group(1).strip()
            out["cert"] = {"not_after": exp,
                           "days": _days_left(exp)}
    except Exception:
        pass
    out["napcat"] = napcat_status()
    out["guard"] = {"secret": bool(guard_secret())}
    return out


def _days_left(text):
    import email.utils
    try:
        ts = email.utils.parsedate_to_datetime(text).timestamp()
        return int((ts - time.time()) // 86400)
    except Exception:
        return None


def napcat_status():
    try:
        r = http_json("http://127.0.0.1:3000/get_login_info", {},
                      headers={"Authorization": "Bearer pojia-napcat-9x4k"}, timeout=5)
        d = r.get("data") or {}
        return {"online": r.get("retcode") == 0, "qq": str(d.get("user_id") or ""),
                "name": d.get("nickname") or ""}
    except Exception as exc:
        return {"online": False, "err": type(exc).__name__}


# ---------------------------------------------------------------- 备份 / 通知
BACKUP_SRC = [
    ("/opt/pojia-cloud/config.json", "pojia-cloud/config.json"),
    ("/opt/pojia-cloud/data/pojia.db", "pojia-cloud/pojia.db"),
    ("/opt/qq-bridge/config.json", "qq-bridge/config.json"),
    ("/opt/qq-bridge/roles", "qq-bridge/roles"),
    ("/opt/qq-bridge/state/current-role.json", "qq-bridge/state/current-role.json"),
    ("/opt/qq-bridge/state/social-v2.json", "qq-bridge/state/social-v2.json"),
    ("/opt/napcat-guard/config.json", "napcat-guard/config.json"),
    ("/opt/pojia-admin/auth.json", "pojia-admin/auth.json"),
]


def backup_make(note=""):
    os.makedirs(BAK_DIR, exist_ok=True)
    name = "pa-%s-%s.tar.gz" % (time.strftime("%Y%m%d-%H%M%S"), secrets.token_hex(2))
    path = os.path.join(BAK_DIR, name)
    manifest = []
    with tarfile.open(path, "w:gz") as tar:
        for src, arc in BACKUP_SRC:
            if not os.path.exists(src):
                continue
            tar.add(src, arcname=arc)
            manifest.append(arc)
    return {"ok": 1, "name": name, "bytes": os.path.getsize(path), "files": manifest, "note": note}


def backup_list():
    out = []
    if os.path.isdir(BAK_DIR):
        for fn in sorted(os.listdir(BAK_DIR), reverse=True):
            p = os.path.join(BAK_DIR, fn)
            if fn.endswith(".tar.gz") and os.path.isfile(p):
                st = os.stat(p)
                out.append({"name": fn, "bytes": st.st_size,
                            "t": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))})
    return out[:40]


def backup_restore(name):
    if not re.fullmatch(r"pa-[\d-]+-[0-9a-f]{4}\.tar\.gz", name or ""):
        return {"ok": 0, "err": "非法备份名"}
    path = os.path.join(BAK_DIR, name)
    if not os.path.isfile(path):
        return {"ok": 0, "err": "备份不存在"}
    backup_make("restore-before-" + name)
    with tarfile.open(path, "r:gz") as tar:
        for m in tar.getmembers():
            if m.name.startswith("/") or ".." in m.name:
                return {"ok": 0, "err": "备份内容异常：%s" % m.name}
        tar.extractall("/")
    return {"ok": 1, "name": name}


def mail_send(subject, text):
    m = (_read_json(CLOUD_CFG).get("mail") or {})
    if not (m.get("host") and m.get("user") and m.get("to")):
        return {"ok": 0, "err": "邮件通道未配置"}
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.header import Header
        msg = MIMEText(text, "plain", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = m.get("user")
        msg["To"] = m.get("to")
        smtp = smtplib.SMTP_SSL(m.get("host"), int(m.get("port") or 465), timeout=15)
        smtp.login(m.get("user"), m.get("pass"))
        smtp.sendmail(m.get("user"), [m.get("to")], msg.as_string())
        smtp.quit()
        return {"ok": 1}
    except Exception as exc:
        return {"ok": 0, "err": "%s: %s" % (type(exc).__name__, exc)}


def notify_test(channel):
    cfg = _read_json(CLOUD_CFG)
    if channel == "mail":
        m = cfg.get("mail") or {}
        r = mail_send("破甲后台 · 通知自检", "pojia-admin 通知通道自检：这封邮件说明 SMTP 配置可用。")
        if r.get("ok"):
            return {"ok": 1, "msg": "邮件已发往 %s" % m.get("to")}
        return r
    if channel == "telegram":
        t = cfg.get("telegram") or {}
        try:
            r = http_json("https://api.telegram.org/bot%s/sendMessage" % t.get("bot_token"),
                          {"chat_id": t.get("chat_id"), "text": "破甲后台 · 通知自检 OK"}, timeout=15)
            return {"ok": 1 if r.get("ok") else 0, "resp": r}
        except Exception as exc:
            return {"ok": 0, "err": "%s: %s" % (type(exc).__name__, exc)}
    return {"ok": 0, "err": "未知通道"}


# ---------------------------------------------------------------- 搜索
def search(q, limit=40):
    q = (q or "").strip()
    if len(q) < 2:
        return {"ok": 0, "err": "至少两个字"}
    like = "%" + q + "%"
    up = q.upper()
    res = {"ok": 1, "q": q, "users": [], "codes": [], "devices": [], "board": []}
    if not os.path.isfile(DB_F):
        return {"ok": 0, "err": "数据库文件不存在"}
    try:
        conn = sqlite3.connect("file:%s?mode=ro" % DB_F, uri=True, timeout=5)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT qq, code, t, ip, last_login, banned FROM users "
                  "WHERE qq LIKE ? OR UPPER(code) LIKE ? OR ip LIKE ? ORDER BY t DESC LIMIT ?",
                  (like, up, like, limit))
        res["users"] = [dict(r) for r in c.fetchall()]
        c.execute("SELECT code, hwid, t, note FROM codes "
                  "WHERE UPPER(code) LIKE ? OR hwid LIKE ? OR note LIKE ? LIMIT ?",
                  (up, like, like, limit))
        res["codes"] = [dict(r) for r in c.fetchall()]
        c.execute("SELECT hwid, code, qq, last_ts, ip, ver, ok FROM devices "
                  "WHERE hwid LIKE ? OR code LIKE ? OR qq LIKE ? OR ip LIKE ? "
                  "ORDER BY last_ts DESC LIMIT ?", (like, up, like, like, limit))
        res["devices"] = [dict(r) for r in c.fetchall()]
        c.execute("SELECT id, ts, cat, qq, nick, text, hide FROM board_posts "
                  "WHERE text LIKE ? OR qq LIKE ? ORDER BY ts DESC LIMIT ?",
                  (like, like, limit))
        res["board"] = [dict(r) for r in c.fetchall()]
        conn.close()
    except Exception as exc:
        return {"ok": 0, "err": "%s: %s" % (type(exc).__name__, exc)}
    return res


# ---------------------------------------------------------------- 只读 SQL
_SQL_HEAD = re.compile(r"^\s*(select|with|pragma|explain)\b", re.I)


def _ro_conn(timeout=8):
    return sqlite3.connect("file:%s?mode=ro" % DB_F, uri=True, timeout=timeout)


def sql_tables():
    """列出库里的表与行数，供 SQL 面板做提示。"""
    out = []
    if not os.path.isfile(DB_F):
        return out
    try:
        conn = _ro_conn(5)
        c = conn.cursor()
        names = [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        for n in names:
            try:
                cnt = c.execute('SELECT COUNT(*) FROM "%s"' % n.replace('"', '""')).fetchone()[0]
            except Exception:
                cnt = -1
            out.append({"name": n, "rows": cnt})
        conn.close()
    except Exception:
        pass
    return out


def sql_run(sql, limit=500):
    """在只读连接上跑一条语句。写操作会被 SQLite 的 mode=ro 直接拒掉。"""
    sql = (sql or "").strip()
    while sql.endswith(";"):
        sql = sql[:-1].rstrip()
    if not sql:
        return {"ok": 0, "err": "SQL 为空"}
    if not _SQL_HEAD.match(sql):
        return {"ok": 0, "err": "只允许只读语句：SELECT / WITH / PRAGMA / EXPLAIN"}
    if ";" in sql:
        return {"ok": 0, "err": "一次只能跑一条语句"}
    if not os.path.isfile(DB_F):
        return {"ok": 0, "err": "数据库文件不存在：%s" % DB_F}
    t0 = time.time()
    try:
        conn = _ro_conn()
        conn.execute("PRAGMA query_only=ON")
        c = conn.cursor()
        c.execute(sql)
        cols = [d[0] for d in (c.description or [])]
        if not cols:                      # PRAGMA 之类没有结果集
            conn.close()
            return {"ok": 1, "cols": [], "rows": [], "ms": int((time.time() - t0) * 1000),
                    "truncated": False}
        rows = c.fetchmany(limit + 1)
        trunc = len(rows) > limit
        rows = rows[:limit]
        conn.close()
        return {"ok": 1, "cols": cols,
                "rows": [[_cell(x) for x in r] for r in rows],
                "truncated": trunc, "ms": int((time.time() - t0) * 1000)}
    except Exception as exc:
        return {"ok": 0, "err": "%s: %s" % (type(exc).__name__, exc)}


def _cell(v):
    if isinstance(v, (bytes, bytearray)):
        return v[:120].hex()
    if isinstance(v, float):
        return round(v, 6)
    return v


# ---------------------------------------------------------------- 巡检 / 告警
def watch_check():
    """一次性体检：返回 problems 列表。systemd timer 每 5 分钟跑一次。"""
    h = health()
    probs = []

    def add(lv, k, msg):
        probs.append({"lv": lv, "k": k, "msg": msg})

    for s in h["services"]:
        if s["state"] != "active":
            # dsh 是 DSH 运行时，平时可能没起，不当作故障
            add("warn" if s["unit"] == "dsh" else "err", "service",
                "%s 未运行（%s）" % (s["unit"], s["state"]))
    must = {443, 80, 8090, 3100, 3110}
    for p in h["ports"]:
        if p["port"] in must and not p["open"]:
            add("err", "port", "端口 %s（%s）不通" % (p["port"], p["label"]))
    mem = ((h["sys"].get("mem") or {}).get("pct") or 0)
    if mem >= 92:
        add("warn", "mem", "内存占用 %s%%" % mem)
    try:
        load1 = float((h["sys"].get("load") or ["0"])[0])
        if load1 > 8:
            add("warn", "load", "1 分钟负载 %s" % load1)
    except Exception:
        pass
    try:
        pct = sh("df --output=pcent / | tail -1").strip().replace("%", "")
        if pct.isdigit() and int(pct) >= 90:
            add("warn", "disk", "磁盘占用 %s%%" % pct)
    except Exception:
        pass
    cert = h.get("cert") or {}
    if isinstance(cert.get("days"), int):
        if cert["days"] < 3:
            add("err", "cert", "证书剩 %s 天，快过期了" % cert["days"])
        elif cert["days"] < 14:
            add("warn", "cert", "证书剩 %s 天" % cert["days"])
    nk = h.get("napcat") or {}
    if not nk.get("online"):
        add("err", "napcat", "NapCat 离线（需要扫码复活）")
    lv = "err" if any(p["lv"] == "err" for p in probs) else ("warn" if probs else "ok")
    return {"t": int(time.time()), "level": lv, "problems": probs,
            "uptime": h["sys"].get("uptime"), "mem": mem}


def watch_hist(n=60):
    rows = []
    if os.path.isfile(WATCH_F):
        try:
            with open(WATCH_F, "r", encoding="utf-8") as f:
                for line in f.readlines()[-n:]:
                    line = line.strip()
                    if line:
                        try:
                            rows.append(json.loads(line))
                        except Exception:
                            pass
        except Exception:
            pass
    return list(reversed(rows))


def watch_once(push=False):
    rec = watch_check()
    heal = autoheal()
    rec["heal"] = heal
    if heal.get("restarted"):
        rec["problems"].append({"lv": "warn", "k": "heal",
                                "msg": "桥接 WebSocket 静默 %.0f 分钟，已自动重启 qq-bridge"
                                       % (heal.get("ago_min") or 0)})
        rec["level"] = "err" if rec["level"] == "err" else "warn"
    prev = (watch_hist(1) or [{}])[0]
    try:
        with open(WATCH_F, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        # 只留最近 2000 条
        lines = open(WATCH_F, "r", encoding="utf-8").readlines()
        if len(lines) > 2000:
            with open(WATCH_F, "w", encoding="utf-8") as f:
                f.writelines(lines[-2000:])
    except Exception:
        pass
    # 状态由好变坏才推送，避免每 5 分钟一封
    if push and rec["level"] != "ok" and prev.get("level") != rec["level"]:
        body = "巡检发现问题（%s）\n\n" % time.strftime("%Y-%m-%d %H:%M", time.localtime(rec["t"]))
        body += "\n".join("· [%s] %s" % (p["lv"], p["msg"]) for p in rec["problems"])
        mail_send("破甲后台 · 巡检告警", body)
    return rec


# ---------------------------------------------------------------- 分组重启
RESTART_GROUPS = {
    "qq": ["qq-bridge", "pojia-qq-easteregg", "pojia-qq-guard", "napcat-guard"],
    "web": ["pojia-cloud", "pojia-code-web", "pojia-site", "pojia-card"],
    "all": ["pojia-cloud", "pojia-code-web", "pojia-site", "pojia-card",
            "qq-bridge", "pojia-qq-easteregg", "pojia-qq-guard", "napcat-guard"],
}


def autoheal():
    """桥接假死自愈：NapCat 账号在线、但桥接的 WebSocket 收不到事件包
    （QQ 重新登录 / NapCat 重启后常见），此时机器人「在线却哑巴」。
    这里直接重启 qq-bridge 让 WS 重连，30 分钟内最多动一次。"""
    try:
        st = qq_api("status")
    except Exception as exc:
        return {"ok": 0, "err": "%s: %s" % (type(exc).__name__, exc)}
    sl = (st or {}).get("snowluma") or {}
    if not sl.get("accountOnline"):
        return {"ok": 1, "skip": "napcat 账号不在线，交给扫码守卫"}
    ago = int(sl.get("lastPacketAgoMs") or 0)
    dead = (not sl.get("connected")) or bool(sl.get("silent"))
    if not dead or ago < 6 * 60 * 1000:
        return {"ok": 1, "skip": "连接正常"}
    rec = _read_json(HEAL_F)
    if time.time() - float(rec.get("ts") or 0) < 1800:
        return {"ok": 1, "skip": "30 分钟内已自愈过，先不动"}
    sh("systemctl restart qq-bridge", 60)
    _write_json(HEAL_F, {"ts": int(time.time()), "ago_ms": ago,
                         "connected": bool(sl.get("connected"))})
    audit("127.0.0.1", "autoheal", "qq-bridge ws 静默 %d 分钟" % (ago // 60000))
    return {"ok": 1, "restarted": True, "ago_min": round(ago / 60000.0, 1)}


def autobak_state():
    """定时备份的当前状态（systemd timer）。"""
    out = {"enabled": None, "active": "", "next": "", "count": len(backup_list())}
    try:
        out["enabled"] = sh("systemctl is-enabled pojia-admin-backup.timer 2>/dev/null").strip() == "enabled"
        out["active"] = sh("systemctl is-active pojia-admin-backup.timer 2>/dev/null").strip()
        line = sh("systemctl list-timers pojia-admin-backup.timer --no-pager --no-legend 2>/dev/null").strip()
        out["next"] = " ".join(line.split()[:3]) if line else ""
    except Exception:
        pass
    return out


def restart_group(group):
    units = RESTART_GROUPS.get(group or "")
    if not units:
        return {"ok": 0, "err": "未知分组"}
    done = []
    for u in units:
        sh("systemctl restart %s" % u, 60)
        done.append({"unit": u, "state": sh("systemctl is-active %s" % u).strip()})
    return {"ok": 1, "items": done}


# ---------------------------------------------------------------- HTTP
class H(BaseHTTPRequestHandler):
    server_version = "pojia-admin/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    # ---------- 输出helper
    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or []):
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except Exception:
            pass

    def _json(self, code, obj, extra=None):
        self._send(code, obj, extra=extra)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        if n > 96 * 1024 * 1024:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8", "replace"))
        except Exception:
            return {}

    def _ip(self):
        return (self.headers.get("X-Real-IP") or self.client_address[0] or "").strip()

    # ---------- 会话
    def _cookie_token(self):
        raw = self.headers.get("Cookie") or ""
        for part in raw.split(";"):
            k, _, v = part.strip().partition("=")
            if k == COOKIE:
                return v
        return ""

    def _signed(self, exp):
        mac = hmac.new(secret(), str(exp).encode(), hashlib.sha256).hexdigest()
        return "%s.%s" % (exp, mac)

    def _session_ok(self):
        tok = self._cookie_token()
        if "." not in tok:
            return False
        exp, _, mac = tok.partition(".")
        want = hmac.new(secret(), exp.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, want):
            return False
        try:
            return int(exp) > time.time()
        except Exception:
            return False

    # ---------- GET
    def do_GET(self):
        u = urlparse(self.path)
        path = u.path
        q = parse_qs(u.query)
        if path in ("/adm", "/adm/", "/"):
            return self._page()
        if not path.startswith("/adm/api/"):
            return self._json(404, {"ok": 0, "err": "not found"})
        api = path[len("/adm/api/"):]
        if api == "me":
            return self._json(200, {"ok": 1, "authed": self._session_ok()})
        if not self._session_ok():
            return self._json(401, {"ok": 0, "err": "未登录"})
        try:
            return self._api_get(api, q)
        except Exception as exc:
            return self._json(500, {"ok": 0, "err": "%s: %s" % (type(exc).__name__, exc)})

    def do_POST(self):
        u = urlparse(self.path)
        path = u.path
        if not path.startswith("/adm/api/"):
            return self._json(404, {"ok": 0, "err": "not found"})
        api = path[len("/adm/api/"):]
        body = self._body()
        if api == "login":
            return self._login(body)
        if api == "logout":
            audit(self._ip(), "logout")
            return self._json(200, {"ok": 1}, extra=[("Set-Cookie", "%s=; Path=/adm; Max-Age=0; HttpOnly; SameSite=Lax" % COOKIE)])
        if not self._session_ok():
            return self._json(401, {"ok": 0, "err": "未登录"})
        try:
            return self._api_post(api, body, u)
        except Exception as exc:
            return self._json(500, {"ok": 0, "err": "%s: %s" % (type(exc).__name__, exc)})

    # ---------- 页面
    def _page(self):
        html = _read(HTML_F)
        if not html:
            return self._send(500, "admin.html 缺失", "text/plain; charset=utf-8")
        self._send(200, html, "text/html; charset=utf-8")

    # ---------- 登录
    def _login(self, body):
        ip = self._ip()
        now = time.time()
        cnt, until = _FAILS.get(ip, [0, 0])
        if until > now:
            return self._json(429, {"ok": 0, "err": "尝试过多，请 %d 秒后再试" % int(until - now)})
        rec = auth_rec()
        pwd = str(body.get("p") or "")
        want = _pw(pwd, rec["salt"], int(rec.get("iter") or 200000))
        if not hmac.compare_digest(want, rec["hash"]):
            cnt += 1
            _FAILS[ip] = [cnt, now + LOGIN_LOCK if cnt >= LOGIN_MAX_FAIL else 0]
            audit(ip, "login-fail", "第 %d 次" % cnt)
            return self._json(403, {"ok": 0, "err": "密码不对"})
        _FAILS.pop(ip, None)
        exp = int(now + SESSION_TTL)
        audit(ip, "login-ok")
        cookie = "%s=%s; Path=/adm; Max-Age=%d; HttpOnly; SameSite=Lax" % (
            COOKIE, self._signed(exp), SESSION_TTL)
        if self.headers.get("X-Forwarded-Proto") == "https":
            cookie += "; Secure"
        return self._json(200, {"ok": 1, "exp": exp}, extra=[("Set-Cookie", cookie)])

    # ---------- GET 路由
    def _api_get(self, api, q):
        if api == "qq/roles/limit":
            # 上游只有 POST，GET 会 404；这里从 /api/roles 的 limits 里取，读操作不发写请求
            r = qq_api("roles")
            lim = (r.get("limits") or {}).get("injectMaxChars")
            return self._json(200, {"ok": 1, "maxInjectChars": lim,
                                    "limits": {"injectMaxChars": lim}})
        if api.startswith("qq/"):
            rest = api[3:]
            url = QQ_BASE + "/api/" + rest
            if q:
                from urllib.parse import urlencode
                url += ("&" if "?" in url else "?") + urlencode(q, doseq=True)
            req = Request(url, headers={"x-console-token": qq_token()})
            with urlopen(req, timeout=60) as r:
                raw = r.read()
                ct = r.headers.get("Content-Type") or "application/json"
            return self._send(200, raw, ct)
        if api == "cloudimg":
            ep = (q.get("ep") or ["ads"])[0]
            ident = (q.get("id") or [""])[0]
            r = cloud_api(ep if ep in ("ads", "guiads", "notice", "donate") else "ads", {})
            items = r.get("items")
            img = r.get("image")
            if items:
                for it in items:
                    if str(it.get("id")) == ident:
                        img = it.get("image")
                        break
            if not img:
                return self._json(404, {"ok": 0, "err": "没有图片"})
            m = re.match(r"data:([^;]+);base64,(.*)$", img, re.S)
            if m:
                return self._send(200, base64.b64decode(m.group(2)), m.group(1))
            return self._send(200, img.encode(), "text/plain")
        if api == "cloudcsv":
            table = (q.get("table") or ["codes"])[0]
            kw = (q.get("q") or [""])[0]
            if table not in ("codes", "users", "devices", "bind", "board", "admin", "reg", "dl"):
                return self._json(400, {"ok": 0, "err": "不支持的导出表"})
            with _LOCK:
                tk = (_read_json(CLOUD_TK_F).get("token") or "") or _cloud_login()
            body = json.dumps({"token": tk, "act": "export", "table": table, "q": kw}).encode()
            req = Request(CLOUD_BASE + "/api/admin/db", data=body,
                          headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=120, context=_SSL) as r:
                raw = r.read()
                ct = r.headers.get("Content-Type") or "text/csv; charset=utf-8"
            audit(self._ip(), "export", table + " " + kw)
            fn = "pojia-%s-%s.csv" % (table, time.strftime("%Y%m%d-%H%M%S"))
            return self._send(200, raw, ct, extra=[("Content-Disposition",
                                                   'attachment; filename="%s"' % fn)])
        if api == "sys/health":
            return self._json(200, health())
        if api == "sys/logs":
            unit = (q.get("unit") or ["pojia-cloud"])[0]
            n = min(int((q.get("n") or ["200"])[0]), 2000)
            if not re.fullmatch(r"[\w.@-]+", unit):
                return self._json(400, {"ok": 0, "err": "unit 非法"})
            return self._json(200, {"ok": 1, "unit": unit,
                                    "text": sh("journalctl -u %s -n %d --no-pager -o short-iso" % (unit, n), 30)})
        if api == "sys/dlog":
            n = min(int((q.get("n") or ["200"])[0]), 2000)
            return self._json(200, {"ok": 1, "text": sh("docker logs --tail %d napcat 2>&1" % n, 30)})
        if api == "sys/backups":
            return self._json(200, {"ok": 1, "items": backup_list()})
        if api == "sys/audit":
            n = min(int((q.get("n") or ["200"])[0]), 2000)
            rows = []
            if os.path.isfile(AUDIT_F):
                try:
                    with open(AUDIT_F, "r", encoding="utf-8") as f:
                        lines = f.readlines()[-n:]
                    rows = [json.loads(x) for x in lines if x.strip()]
                except Exception:
                    rows = []
            return self._json(200, {"ok": 1, "items": list(reversed(rows))})
        if api == "sys/search":
            return self._json(200, search((q.get("q") or [""])[0]))
        if api == "sys/sql/tables":
            return self._json(200, {"ok": 1, "items": sql_tables()})
        if api == "sys/watch":
            n = min(int((q.get("n") or ["60"])[0]), 500)
            h = watch_hist(n)
            return self._json(200, {"ok": 1, "now": h[0] if h else watch_check(),
                                    "items": h, "bak": backup_list()[:3],
                                    "autobak": autobak_state()})
        if api == "napcat/status":
            return self._json(200, dict(napcat_status(), guard=guard_secret()))
        if api == "napcat/qr.png":
            sec = guard_secret()
            if not sec:
                return self._json(404, {"ok": 0, "err": "读不到守卫密钥"})
            with urlopen(GUARD_BASE + "/qr/%s/qr.png" % sec, timeout=8) as r:
                raw = r.read()
                self._send(200, raw, r.headers.get("Content-Type") or "image/png")
            return
        if api.startswith("cloud/"):
            return self._json(200, cloud_api(api[6:], {}))
        return self._json(404, {"ok": 0, "err": "no route %s" % api})

    # ---------- POST 路由
    def _api_post(self, api, body, u):
        ip = self._ip()
        if api.startswith("qq/"):
            rest = api[3:]
            url = QQ_BASE + "/api/" + rest
            if u.query:
                url += "?" + u.query
            r = http_json(url, body, headers={"x-console-token": qq_token()}, timeout=120)
            if rest.split("?")[0] not in ("test-send", "socialV2/activity", "tokens/summary"):
                audit(ip, "qq:" + rest.split("?")[0], json.dumps(body, ensure_ascii=False)[:200])
            return self._json(200, r)
        if api.startswith("cloud/"):
            name = api[6:]
            r = cloud_api(name, body)
            audit(ip, "cloud:" + name, json.dumps(body, ensure_ascii=False)[:200])
            return self._json(200, r)
        if api == "sys/backup":
            r = backup_make(str(body.get("note") or ""))
            audit(ip, "backup", r.get("name", ""))
            return self._json(200, r)
        if api == "sys/sql":
            r = sql_run(str(body.get("sql") or ""))
            audit(ip, "sql", str(body.get("sql") or "")[:200])
            return self._json(200, r)
        if api == "sys/watch/run":
            r = watch_once()
            audit(ip, "watch", r.get("level", ""))
            return self._json(200, r)
        if api == "sys/heal":
            r = autoheal()
            audit(ip, "heal", json.dumps(r, ensure_ascii=False)[:160])
            return self._json(200, r)
        if api == "sys/restart-group":
            g = str(body.get("group") or "")
            r = restart_group(g)
            audit(ip, "restart-group", g)
            return self._json(200, r)
        if api == "sys/restore":
            r = backup_restore(str(body.get("name") or ""))
            audit(ip, "restore", str(body.get("name") or ""))
            return self._json(200, r)
        if api == "sys/restart":
            unit = str(body.get("unit") or "")
            if unit not in [s[0] for s in SERVICES]:
                return self._json(400, {"ok": 0, "err": "不允许重启该服务"})
            out = sh("systemctl restart %s" % unit, 60)
            audit(ip, "restart", unit)
            time.sleep(1)
            return self._json(200, {"ok": 1, "state": sh("systemctl is-active %s" % unit).strip(), "out": out[:400]})
        if api == "sys/notify":
            ch = str(body.get("ch") or "mail")
            r = notify_test(ch)
            audit(ip, "notify", ch)
            return self._json(200, r)
        if api == "napcat/restart":
            out = sh("docker restart napcat", 90)
            audit(ip, "napcat-restart", "")
            return self._json(200, {"ok": 1, "out": out[:400]})
        if api == "auth/passwd":
            old = str(body.get("old") or "")
            new = str(body.get("new") or "")
            rec = auth_rec()
            if not hmac.compare_digest(_pw(old, rec["salt"], int(rec["iter"])), rec["hash"]):
                return self._json(403, {"ok": 0, "err": "原密码不对"})
            if len(new) < 8:
                return self._json(400, {"ok": 0, "err": "新密码至少 8 位"})
            salt = secrets.token_hex(16)
            rec.update({"salt": salt, "iter": 200000, "hash": _pw(new, salt, 200000)})
            _write_json(AUTH_F, rec)
            audit(ip, "passwd", "")
            return self._json(200, {"ok": 1})
        return self._json(404, {"ok": 0, "err": "no route %s" % api})


def main():
    os.makedirs(ROOT, exist_ok=True)
    os.makedirs(BAK_DIR, exist_ok=True)
    auth_rec()  # 种子账号/密码
    secret()
    if "--watch" in sys.argv:          # 巡检模式（systemd timer 调用）
        rec = watch_once(push=True)
        print(json.dumps(rec, ensure_ascii=False))
        return
    if "--autobak" in sys.argv:        # 自动备份模式（systemd timer 调用）
        keep = int(os.environ.get("PA_BAK_KEEP", "14"))
        r = backup_make("auto")
        items = backup_list()
        for old in items[keep:]:
            try:
                os.remove(os.path.join(BAK_DIR, old["name"]))
            except Exception:
                pass
        print(json.dumps({"ok": r.get("ok"), "name": r.get("name"),
                          "kept": min(len(items), keep)}, ensure_ascii=False))
        return
    srv = ThreadingHTTPServer((BIND, PORT), H)
    print("pojia-admin listening %s:%d" % (BIND, PORT), flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
