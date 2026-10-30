# -*- coding: utf-8 -*-
import paramiko, base64
c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("23.224.194.7",22,"root","36925814Aa",timeout=25,look_for_keys=False,allow_agent=False)
def sh(cmd,t=180):
    _,o,e=c.exec_command(cmd,timeout=t)
    return o.read().decode("utf-8","replace")+e.read().decode("utf-8","replace")

def put(remote, text):
    b64=base64.b64encode(text.encode()).decode()
    sh("printf '%s' '%s' | base64 -d > %s" % ("%s", b64, remote))
    print(remote, sh("wc -c < "+remote).strip())

put("/etc/systemd/system/pojia-admin-backup.service", """[Unit]
Description=pojia-admin 自动备份（打包云配置/数据库/人格/状态）
After=network.target

[Service]
Type=oneshot
Environment=PA_ROOT=/opt/pojia-admin
Environment=PA_BAK_KEEP=14
ExecStart=/usr/bin/python3 /opt/pojia-admin/admin.py --autobak
""")

put("/etc/systemd/system/pojia-admin-backup.timer", """[Unit]
Description=pojia-admin 每天 04:10 自动备份

[Timer]
OnCalendar=*-*-* 04:10:00
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
""")

put("/etc/systemd/system/pojia-admin-watch.service", """[Unit]
Description=pojia-admin 巡检（服务/端口/内存/磁盘/证书/NapCat）
After=network.target

[Service]
Type=oneshot
Environment=PA_ROOT=/opt/pojia-admin
ExecStart=/usr/bin/python3 /opt/pojia-admin/admin.py --watch
""")

put("/etc/systemd/system/pojia-admin-watch.timer", """[Unit]
Description=pojia-admin 每 5 分钟巡检一次

[Timer]
OnBootSec=90s
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
""")

print(sh("systemctl daemon-reload && systemctl enable --now pojia-admin-backup.timer pojia-admin-watch.timer 2>&1"))
print(sh("systemctl list-timers 'pojia-admin*' --no-pager"))
print(sh("sleep 3; tail -n 2 /opt/pojia-admin/watch.jsonl"))
c.close()
