import io, os, re, sys, time

P = "/opt/pojia-cloud/pojia_serve.py"
s = open(P, encoding="utf-8").read()
if "def _h_adm(self)" in s:
    print("already patched")
    sys.exit(0)

H_ADM = '''    def _h_adm(self):
        """2026-10-30：443 上没有 nginx，这里自己把 /adm 反代到 127.0.0.1:3120，
        这样 https://域名/adm/ 和 http://IP/adm/ 都是同一个后台。"""
        import urllib.request as _ur
        path = self.path if self.path.startswith("/adm") else "/adm" + self.path
        method = self.command
        data = None
        hdrs = {"X-Real-IP": (self.client_address[0] if self.client_address else "")}
        _ck = self.headers.get("Cookie")
        if _ck:
            hdrs["Cookie"] = _ck[:8192]
        if method in ("POST", "PUT", "PATCH"):
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                n = 0
            data = self.rfile.read(n) if n else b""
            hdrs["Content-Type"] = self.headers.get("Content-Type", "application/json")
        req = _ur.Request("http://127.0.0.1:3120" + path, data=data,
                          headers=hdrs, method=method)
        sets = []
        try:
            with _ur.urlopen(req, timeout=180) as resp:
                b = resp.read()
                st = resp.status
                ct = resp.headers.get("Content-Type", "application/json")
                sets = resp.headers.get_all("Set-Cookie") or []
                cd = resp.headers.get("Content-Disposition")
        except _ur.HTTPError as he:
            b = he.read()
            st = he.code
            ct = he.headers.get("Content-Type", "application/json")
            sets = he.headers.get_all("Set-Cookie") or []
            cd = he.headers.get("Content-Disposition")
        except Exception:
            return self._json(502, {"ok": 0, "err": "admin upstream down"})
        self.send_response(st)
        self.send_header("Content-Type", ct)
        for _s in sets:
            self.send_header("Set-Cookie", _s)
        if cd:
            self.send_header("Content-Disposition", cd)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(b)
        except Exception:
            pass

'''

anchor = "    def _h_proxy_admin(self):"
assert anchor in s, "找不到 _h_proxy_admin"
s = s.replace(anchor, H_ADM + anchor, 1)

old_body = '''    def _h_proxy_admin(self):
        return self._proxy_web("/admin")'''
new_body = '''    def _h_proxy_admin(self):
        # 2026-10-30：旧管理后台（webui/admin.html）已下线，统一跳新后台
        self.send_response(302)
        self.send_header("Location", "/adm/")
        self.send_header("Content-Length", "0")
        self.end_headers()'''
assert old_body in s, "找不到旧 _h_proxy_admin 主体"
s = s.replace(old_body, new_body, 1)

g_anchor = "    (_m_dead_portal_410, Handler._h_dead_portal_410),"
assert g_anchor in s, "找不到 GET 前缀锚点"
s = s.replace(g_anchor,
              '    (lambda _po, _full: _po == "/adm" or _po.startswith("/adm/"), Handler._h_adm),\n' + g_anchor, 1)

p_anchor = '        _po = self.path.split("?", 1)[0]\n        if _po == "/pojia/admin/guiads":'
assert p_anchor in s, "找不到 POST 锚点"
s = s.replace(p_anchor,
              '        _po = self.path.split("?", 1)[0]\n'
              '        if _po == "/adm" or _po.startswith("/adm/"):\n'
              '            return self._h_adm()\n'
              '        if _po == "/pojia/admin/guiads":', 1)

open(P, "w", encoding="utf-8").write(s)
print("patched ok")
