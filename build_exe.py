# -*- coding: utf-8 -*-
"""把 破甲一键通.py 打成**单文件 exe**（给没装 Python 的人用）。

为什么需要它、以及为什么不能只敲一条 pyinstaller 命令 —— 两个坑，少一个 exe 就是坏的：

1) **随包源码副本**
   脚本有两层自校验（_k2 派生解密密钥 / _d2 整文件封条），两者都要"源码文本"。
   冻结后磁盘上没有明文源码，`_seal_read_source()` 会去读 `_MEIPASS` 下的
   `_pojia_src.py`。这个文件必须恰好是**签名时的那一份字节**，否则：
     · 缺了 → 启动即 exit 3（错误信息："源码层不可用：frozen 运行但随包源码副本缺失"）；
     · 内容不一致 → 密钥失配 → 同样 exit 3。
   所以本脚本在构建前**把当前 .py 原样复制**成 `_pojia_src.py` 再 `--add-data` 带进去。

2) **工作目录**
   frozen 时 `__file__` 指向 `%TEMP%\\_MEIxxxx`（进程退出即删）。脚本内部已改成
   `HERE = exe 所在目录`，所以《历史备份/》《状态/》《破甲日志.txt》《persona.md》
   都落在 exe 旁边 —— 和 .py 版行为一致。**不要把 exe 放在只读目录或压缩包里直接运行。**

用法：
    python build_exe.py                 # 单文件 console exe -> dist/
    python build_exe.py --zip           # 额外打一个给小白的一键包
"""
import os
import shutil
import subprocess
import sys
import zipfile

REPO = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(REPO, "破甲一键通.py")
NAME = "破甲一键通"
WORK = os.path.join(REPO, "_build")
DIST = os.path.join(REPO, "dist")
SRC_COPY = os.path.join(WORK, "_pojia_src.py")


def main():
    if not os.path.isfile(SCRIPT):
        print("找不到主脚本：%s" % SCRIPT)
        return 2

    # ---- 0) 先确认主脚本自身能起来（封条完好），否则打出来的 exe 也是死的 ----
    r = subprocess.run([sys.executable, SCRIPT, "--version"], capture_output=True)
    ver = r.stdout.decode("utf-8", "replace").strip()
    if r.returncode != 0:
        print("主脚本自身校验未通过（exit %s），先修好再打包。" % r.returncode)
        print(r.stdout.decode("utf-8", "replace")[:800])
        return 1
    print("主脚本自检通过：%s" % ver)

    os.makedirs(WORK, exist_ok=True)
    # ---- 1) 把签名时的那份源码原样复制出来（必须逐字节一致）----
    shutil.copy2(SCRIPT, SRC_COPY)
    import hashlib
    h1 = hashlib.sha256(open(SCRIPT, "rb").read()).hexdigest()
    h2 = hashlib.sha256(open(SRC_COPY, "rb").read()).hexdigest()
    if h1 != h2:
        print("源码副本与主脚本不一致，终止。")
        return 1
    print("随包源码副本已就绪（sha256 %s…，%d 字节）" % (h1[:16], os.path.getsize(SRC_COPY)))

    # ---- 2) PyInstaller ----
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile",              # 单文件：小白只需要一个 exe
        "--console",              # 保留控制台 —— 交互菜单就是它唯一的界面
        "--noupx",                # 不用 UPX：压过的 exe 更容易被杀软误报
        "--name", NAME,
        "--distpath", DIST,
        "--workpath", os.path.join(WORK, "work"),
        "--specpath", os.path.join(WORK, "spec"),
        "--add-data", "%s%c." % (SRC_COPY, os.pathsep),
        SCRIPT,
    ]
    print("PyInstaller:", " ".join(args[:6]), "...")
    r = subprocess.run(args, cwd=REPO)
    if r.returncode != 0:
        print("PyInstaller 失败，exit %s" % r.returncode)
        return r.returncode

    exe = os.path.join(DIST, NAME + ".exe")
    if not os.path.isfile(exe):
        # 中文名偶尔会被工具链改写，退一步找 dist 里唯一的 exe
        cands = [f for f in os.listdir(DIST) if f.lower().endswith(".exe")] if os.path.isdir(DIST) else []
        if len(cands) == 1:
            exe = os.path.join(DIST, cands[0])
        else:
            print("没找到产出的 exe，dist 内容：%s" % cands)
            return 1
    print("\n已产出：%s（%.1f MB）" % (exe, os.path.getsize(exe) / 1048576))

    # ---- 3) 冒烟：用真 exe 跑三条只读命令 ----
    print("\n--- 用真 exe 冒烟 ---")
    ok = True
    for cmd in (["--version"], ["--check"], ["--status"]):
        rr = subprocess.run([exe] + cmd, capture_output=True, cwd=DIST, timeout=180)
        flag = "OK " if rr.returncode == 0 else "FAIL"
        if rr.returncode != 0:
            ok = False
        print("  [%s] %s  exit=%s" % (flag, " ".join(cmd), rr.returncode))
        if rr.returncode != 0:
            print("       " + rr.stdout.decode("utf-8", "replace")[:400].replace("\n", "\n       "))
    if not ok:
        print("\n冒烟未通过 —— exe 不可交付。")
        return 1
    print("冒烟通过。")

    # ---- 4) 可选：打小白包 ----
    if "--zip" in sys.argv:
        zpath = os.path.join(DIST, "pojia-next-v%s-exe.zip" % ver.split()[-1])
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(exe, os.path.join("破甲一键通-v%s" % ver.split()[-1], NAME + ".exe"))
            for extra in ("persona.md", "使用说明.md", "README.md", "LICENSE"):
                p = os.path.join(REPO, extra)
                if os.path.isfile(p):
                    z.write(p, os.path.join("破甲一键通-v%s" % ver.split()[-1], extra))
        print("已打包：%s（%.1f MB）" % (zpath, os.path.getsize(zpath) / 1048576))
    return 0


if __name__ == "__main__":
    sys.exit(main())
