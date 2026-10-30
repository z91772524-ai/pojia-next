# -*- coding: utf-8 -*-
"""关闭两个旧后台入口：pj80 的 /admin 与 qqbridge 的 8091 控制台，统一跳到 /adm/。幂等。"""
import paramiko, time
c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("23.224.194.7",22,"root","36925814Aa",timeout=25,look_for_keys=False,allow_agent=False)
def sh(cmd,t=180):
    _,o,e=c.exec_command(cmd,timeout=t)
    return o.read().decode("utf-8","replace")+e.read().decode("utf-8","replace")

ts=time.strftime("%Y%m%d-%H%M%S")
sh("mkdir -p /root/nginx-bak && cp -f /etc/nginx/sites-available/pj80 /root/nginx-bak/pj80.bak-closeadmin-%s && "
   "cp -f /etc/nginx/sites-available/qqbridge /root/nginx-bak/qqbridge.bak-closeadmin-%s" % (ts, ts))

py = r'''
import sys
p="/etc/nginx/sites-available/pj80"
s=open(p,encoding="utf-8").read()
if "旧管理后台已下线" in s:
    print("pj80: 已处理过，跳过"); sys.exit(0)
old = """    location = /admin { proxy_pass https://127.0.0.1:443; proxy_ssl_verify off;
        proxy_set_header Host $host; proxy_set_header X-Real-IP $remote_addr; }
    location ^~ /admin/ { proxy_pass https://127.0.0.1:443; proxy_ssl_verify off;
        proxy_set_header Host $host; proxy_set_header X-Real-IP $remote_addr; }"""
new = """    # 2026-10-30：旧管理后台（webui/admin.html，22 个面板）已下线，统一跳到新后台 /adm/
    location = /admin { return 302 /adm/; }
    location ^~ /admin/ { return 302 /adm/; }"""
if old not in s:
    print("pj80: 没找到旧 /admin 段落，未改动"); sys.exit(2)
open(p,"w",encoding="utf-8").write(s.replace(old,new,1))
print("pj80: 已把 /admin 换成 302 -> /adm/")
'''
open("/tmp/_p1.py","w").write(py)
print(sh("python3 /tmp/_p1.py"))

qqb = """# qq-bridge 控制台（旧 console.html，8091）已于 2026-10-30 下线。
# 大肥鱼的日常管理统一走新后台 /adm/（它内部反代 127.0.0.1:3100 的 /api/*，
# 所以桥接本身不需要对外暴露任何页面）。
# 原始配置备份：/root/nginx-bak/qqbridge.bak-closeadmin-*.bak
server {
    listen 8091;
    server_name _;
    access_log /var/log/nginx/qqbridge.log;
    error_log  /var/log/nginx/qqbridge.error.log;

    location / {
        return 302 http://$host/adm/;
    }
}
"""
import base64
sh("printf '%s' '%s' | base64 -d > /etc/nginx/sites-available/qqbridge" %
   ("%s", base64.b64encode(qqb.encode()).decode()))
print("---- qqbridge now ----")
print(sh("cat /etc/nginx/sites-available/qqbridge"))
print("---- nginx -t ----")
print(sh("nginx -t 2>&1"))
c.close()
