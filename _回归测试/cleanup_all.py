# -*- coding: utf-8 -*-
"""清场脚本：杀掉所有 破甲一键通GUI.exe 实例 + 删除验证存档残留"""
import subprocess
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

TARGET = "破甲一键通GUI.exe"

# 1) 列出目标进程
r = subprocess.run(["taskkill", "/F", "/IM", TARGET],
                   capture_output=True)
out = (r.stdout or b"").decode("gbk", errors="replace")
err = (r.stderr or b"").decode("gbk", errors="replace")
print("taskkill exit=%d" % r.returncode)
print("stdout=" + out.strip())
if err.strip():
    print("stderr=" + err.strip())

# 2) 确认无残留
r2 = subprocess.run(["tasklist", "/FI", "IMAGENAME eq " + TARGET],
                    capture_output=True)
tl = (r2.stdout or b"").decode("gbk", errors="replace")
if TARGET in tl:
    print("RESIDUE=YES")
else:
    print("RESIDUE=NO (全部清干净)")

# 3) 删除验证存档残留（%APPDATA%\破甲一键通\cloud.json）
appdata = os.environ.get("APPDATA", "")
paths = [
    os.path.join(appdata, "破甲一键通", "cloud.json"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "破甲一键通", "cloud.json"),
]
for p in paths:
    if os.path.exists(p):
        os.remove(p)
        print("DELETED=" + p)
    else:
        print("ABSENT=" + p)
