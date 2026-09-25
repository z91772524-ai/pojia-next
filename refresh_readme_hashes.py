# -*- coding: utf-8 -*-
"""把 README 里"当前版本核心文件"表格的哈希/字节数刷成实际值（v7.5 用）。

fill_hashes.py 只处理 <!--HASH-XX--> 占位符；这张表在发布后是**字面量**，
改了 .py 就必须跟着刷，否则用户按表校验会失败（这个坑踩过一次）。
"""
import hashlib
import io
import os
import re
import sys

R = r"E:\DSH-Workspace\破甲next-github"
TARGETS = ("破甲一键通.py", "一键破甲.bat", "persona.md")


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def main():
    readme = os.path.join(R, "README.md")
    s = io.open(readme, encoding="utf-8").read()
    n = 0
    for name in TARGETS:
        p = os.path.join(R, name)
        if not os.path.exists(p):
            continue
        h = sha256(p)
        size = os.path.getsize(p)
        pat = re.compile(r"(\| `" + re.escape(name) + r"` \| `)([0-9a-f]{8,64})(`… \| )(\d+)( \|)")
        new = pat.sub(lambda m: m.group(1) + h[:32] + m.group(3) + str(size) + m.group(5), s)
        if new != s:
            n += 1
            print("  已刷新 %s -> %s… %d 字节" % (name, h[:32], size))
        s = new
    # newline="\n" 是关键：不加的话 Windows 下会把整份 README 从 LF 写成 CRLF，
    # 一个哈希的小改动会变成 500+ 行的换行符噪音 diff。
    io.open(readme, "w", encoding="utf-8", newline="\n").write(s)
    print("刷新 %d 行（%d 个文件）" % (n, len(TARGETS)))
    # 自检：README 里出现的哈希必须与磁盘一致
    bad = []
    for name in TARGETS:
        p = os.path.join(R, name)
        h = sha256(p)
        if h[:32] not in s:
            bad.append(name)
    if bad:
        print("!! 仍不一致：%s" % bad)
        return 1
    print("自检通过：README 里的三个哈希都与磁盘一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
