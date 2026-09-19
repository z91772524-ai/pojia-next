"""回归测试：验证只读路径不再提问、_pick_targets 输入校验正确。
用桩替换 input，模拟非交互环境，捕获任何意外的 input 调用。
"""
import sys, os, io, importlib.util, traceback

sys.stdout.reconfigure(encoding="utf-8")
SRC = r"E:\DSH-Workspace\破甲next-github\破甲一键通.py"

# --- 载入模块 ---
spec = importlib.util.spec_from_file_location("pj", SRC)
mod = importlib.util.module_from_spec(spec)
sys.argv = ["x"]
spec.loader.exec_module(mod)

ASKED = []

class NoInput:
    def __init__(self, replies=None):
        self.replies = list(replies or [])
    def __call__(self, prompt=""):
        ASKED.append(prompt)
        if self.replies:
            return self.replies.pop(0)
        raise AssertionError("UNEXPECTED INPUT PROMPT: %r" % prompt)

# --- 构造 args ---
class A: pass
def mkargs(**kw):
    a = A()
    a.target = "all"; a.yes = False; a.quiet = False
    a.diagnose = False; a.dry_run = False
    for k, v in kw.items():
        setattr(a, k, v)
    return a

def section(t):
    print("\n" + "=" * 60)
    print(t)
    print("=" * 60)

# ---- T1: run_status 在交互模式下也不得提问 ----
section("T1  run_status 只读，不得提问")
ASKED.clear()
_orig_input = mod.__builtins__["input"] if isinstance(mod.__builtins__, dict) else __builtins__["input"]
import builtins
builtins.input = NoInput()
buf = io.StringIO(); old = sys.stdout; sys.stdout = buf
try:
    mod.run_status(mkargs(), ["dsh", "wb", "zcode"])
    ok1 = True; err1 = ""
except AssertionError as e:
    ok1 = False; err1 = str(e)
except Exception as e:
    ok1 = True; err1 = "非提问异常(可接受): %s" % type(e).__name__
finally:
    sys.stdout = old; builtins.input = _orig_input
print("结果:", "PASS —— 全程未提问" if ok1 else "FAIL —— %s" % err1)
print("提问次数:", len(ASKED))

# ---- T2: dry-run（预演）不得提问 ----
section("T2  run_action(dry-run) 只读，不得提问")
ASKED.clear()
builtins.input = NoInput()
buf = io.StringIO(); old = sys.stdout; sys.stdout = buf
try:
    mod.run_action(mkargs(), "dry-run", ["dsh", "wb", "zcode"])
    ok2 = True; err2 = ""
except AssertionError as e:
    ok2 = False; err2 = str(e)
except Exception as e:
    ok2 = True; err2 = "非提问异常(可接受): %s" % type(e).__name__
finally:
    sys.stdout = old; builtins.input = _orig_input
print("结果:", "PASS —— 全程未提问" if ok2 else "FAIL —— %s" % err2)
print("提问次数:", len(ASKED))

# ---- T3: _pick_targets 非法输入应重问而不是静默返回空 ----
section("T3  _pick_targets 非法输入 -> 重问；输 0 -> 取消")
for case, replies, expect in [
    ("输 '9' 然后 '12'", ["9", "12"], ["dsh", "wb"]),
    ("输 'abc' 然后 '3'", ["abc", "3"], ["zcode"]),
    ("输 '' (回车)",     [""],      []),
    ("输 '0'",           ["0"],     []),
    ("输 '4'",           ["4"],     "all-like"),
]:
    ASKED.clear()
    builtins.input = NoInput(replies)
    buf = io.StringIO(); old = sys.stdout; sys.stdout = buf
    try:
        got = mod._pick_targets(mkargs(), "测试")
    except Exception as e:
        got = "EXC:%s" % e
    finally:
        sys.stdout = old; builtins.input = _orig_input
    if expect == "all-like":
        passfail = "PASS" if isinstance(got, list) and len(got) > 0 else "FAIL"
    else:
        passfail = "PASS" if got == expect else "FAIL"
    print(f"  {case:22s} -> {got!r}  期望{expect!r}  [{passfail}]  问询{len(ASKED)}次")
