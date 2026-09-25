# -*- coding: utf-8 -*-
"""发布助手：生成 SHA256SUMS.txt + 打包 Release 附件 + 打印给 README 用的哈希表。

用法：
    python release.py            # 生成清单 + 打包（不改远端）
    python release.py --print    # 只打印当前文件的哈希（用于更新 README）
"""
import hashlib
import os
import subprocess
import sys
import zipfile

REPO = r"E:\DSH-Workspace\破甲next-github"
DIST = r"E:\DSH-Workspace\破甲next-发布素材"

# Release 附件里放哪些（v7.5 起把 preview.png 也带上：README 引用了它，
# 不带的话解压出来的 README 里那张预览图是坏图）
ASSETS = ["破甲一键通.py", "一键破甲.bat", "persona.md", "使用说明.md",
          "修复报告.md", "README.md", "LICENSE", "preview.png", "赞赏码.png"]
# 清单里额外列出的仓库文件（进 SHA256SUMS.txt，但**不**塞进 Release 附件的 zip）。
# ⚠ 这个列表必须和 SHA256SUMS.txt 的实际条目对齐：漏了的话，下一次跑本脚本
#   会把这些条目从清单里冲掉，用户按 README 校验就会失败（踩过一次）。
EXTRA = ["反抄袭通告.md",
         "evidence/2026-09-25-group-notice.png",
         "evidence/2026-09-25-group-chat.png",
         "evidence/2026-09-25-douyin-profile.jpg",
         "evidence/2026-09-25-2057-group-question.jpg",
         "evidence/2026-09-25-2057-group-notice-revised.jpg"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 16), b""):
            h.update(b)
    return h.hexdigest()


def version():
    for line in open(os.path.join(REPO, "破甲一键通.py"), encoding="utf-8"):
        if line.startswith("VERSION = "):
            return line.split("=")[1].strip().strip('"')
    return "?"


def main():
    ver = version()
    print("版本:", ver)

    if "--print" in sys.argv:
        for f in ASSETS:
            p = os.path.join(REPO, f)
            if os.path.exists(p):
                print("| `%s` | `%s` | %d |" % (f, sha256(p), os.path.getsize(p)))
        return 0

    # 1) 生成 SHA256SUMS.txt（放进仓库，README 与 Release 都引用它）
    lines = ["# 破甲一键通 v%s —— SHA256 校验清单" % ver,
             "# 校验方法（Windows PowerShell）:",
             "#   Get-FileHash .\\破甲一键通.py -Algorithm SHA256",
             "# 校验方法（Linux/macOS）:",
             "#   sha256sum 破甲一键通.py",
             ""]
    for f in ASSETS + EXTRA:
        p = os.path.join(REPO, f)
        if os.path.exists(p):
            lines.append("%s  %s" % (sha256(p), f))
    sums = os.path.join(REPO, "SHA256SUMS.txt")
    with open(sums, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print("已写", sums)

    # 2) 打印给 README 的表格
    print("\n--- README 表格用 ---")
    for f in ASSETS:
        p = os.path.join(REPO, f)
        if os.path.exists(p):
            print("| `%s` | %s | %d |" % (f, sha256(p)[:32] + "…", os.path.getsize(p)))

    # 3) 打 zip（外层文件夹 + zip 里附 SHA256SUMS.txt）
    zip_path = os.path.join(DIST, "pojia-next-v%s.zip" % ver)
    stage = os.path.join(DIST, "_stage_%s" % ver.replace(".", ""))
    inner = os.path.join(stage, "破甲一键通-v%s" % ver)
    if os.path.isdir(stage):
        subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", stage], capture_output=True)
    os.makedirs(inner, exist_ok=True)
    for f in ASSETS + ["SHA256SUMS.txt"]:
        p = os.path.join(REPO, f)
        if os.path.exists(p):
            subprocess.run(["cmd", "/c", "copy", "/y", p, inner], capture_output=True)
    if os.path.exists(zip_path):
        os.remove(zip_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _d, files in os.walk(inner):
            for fn in files:
                full = os.path.join(root, fn)
                z.write(full, os.path.relpath(full, stage))
    subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", stage], capture_output=True)
    print("\n已打包:", zip_path, os.path.getsize(zip_path), "字节")
    print("zip sha256:", sha256(zip_path))
    with zipfile.ZipFile(zip_path) as z:
        print("条目:", len(z.namelist()))
        for n in z.namelist():
            print("   ", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
