# -*- coding: utf-8 -*-
"""把真实 SHA256 填进 README 的占位符（发布前跑一次）。

为什么要"填进去"而不是让文档自己算：往 README 里写哈希会改掉 README 自己的哈希，
所以 README 与 SHA256SUMS.txt 天然不进清单；但核心文件（脚本/启动器/人格）的哈希
是稳定的，适合直接贴在 README 里让人一眼核对。

用法：
    python fill_hashes.py            # 用 SHA256SUMS.txt 里的真实值替换占位符并打印结果
"""
import hashlib
import os
import re
import sys

sys.dont_write_bytecode = True
REPO = os.path.dirname(os.path.abspath(__file__))
README = os.path.join(REPO, "README.md")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 16), b""):
            h.update(b)
    return h.hexdigest()


def short(p, n=32):
    return sha256(p)[:n]


def main():
    mapping = {
        "<!--HASH-PY-->": short(os.path.join(REPO, "破甲一键通.py")),
        "<!--HASH-BAT-->": short(os.path.join(REPO, "一键破甲.bat")),
        "<!--HASH-PERSONA-->": short(os.path.join(REPO, "persona.md")),
    }
    # 注意：**不要**把 Release 附件自身的哈希写进 README —— 附件里装着 README，
    # 那样改一处就两处对不上（循环引用）。附件的哈希只放 Release 正文。
    zp = os.path.join(r"E:\DSH-Workspace\破甲next-发布素材", "pojia-next-v7.5.zip")
    if "<!--HASH-ZIP-->" in open(README, encoding="utf-8").read() and os.path.exists(zp):
        print("  [警告] README 里还有附件哈希占位符，建议删掉（循环引用）")

    t = open(README, encoding="utf-8").read()
    for k, v in mapping.items():
        t = t.replace(k, v)
    with open(README, "w", encoding="utf-8", newline="\n") as f:
        f.write(t)
    for k, v in mapping.items():
        print("  %-20s -> %s" % (k, v))
    left = re.findall(r"<!--HASH-[A-Z]+-->", t)
    print("  剩余占位符:", left or "无")
    return 1 if left else 0


if __name__ == "__main__":
    sys.exit(main())
