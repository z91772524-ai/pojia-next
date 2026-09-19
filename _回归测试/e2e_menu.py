"""端到端演练：模拟菜单点 [1]，验证它会先问目标而不是直接全打。"""
import sys, io, importlib.util, builtins
sys.stdout.reconfigure(encoding="utf-8")
SRC = r"E:\DSH-Workspace\破甲next-github\破甲一键通.py"
spec = importlib.util.spec_from_file_location("pj", SRC)
mod = importlib.util.module_from_spec(spec)
sys.argv = ["x"]
spec.loader.exec_module(mod)

class A: pass
a = A()
a.target = "all"; a.yes = False; a.quiet = False
a.diagnose = False; a.dry_run = False

ASK = []
# 模拟：菜单选 1 -> 目标勾选输 "2" -> 确认 n -> 返回
replies = ["1", "2", "n", ""]
def fake_input(p=""):
    ASK.append(p)
    return replies.pop(0) if replies else ""

builtins.input = fake_input
buf = io.StringIO(); old = sys.stdout; sys.stdout = buf
try:
    mod.menu(a)
finally:
    sys.stdout = old

out = buf.getvalue()
# 去掉 ANSI
import re
clean = re.sub(r'\x1b\[[0-9;]*m', '', out)

print("=== 提问序列 ===")
for i, p in enumerate(ASK, 1):
    print(f"  {i}. {p.strip()}")

print("\n=== 关键断言 ===")
joined = " || ".join(ASK)
c1 = "请选择 (0-9)" in joined
c2 = any("输入序号" in p for p in ASK)          # 出现了目标勾选
c3 = "确认执行？" in joined                       # 出现二次确认
print(f"  菜单出现:                 {c1}")
print(f"  点1后先问目标:            {c2}")
print(f"  之后有二次确认:           {c3}")

print("\n=== 目标勾选界面原文 ===")
idx = clean.find("一键破甲 —— 选要处理的目标")
print(clean[idx-4:idx+520] if idx >= 0 else "(未找到)")
