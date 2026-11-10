# HANDOFF · 破甲一键通交接文档

> 写给下一个接手的人 / AI。读完这一份 + `MEMORY.md`，就能独立改代码、发版、排障。
> 最后更新：2026-11-08 11:10 · 对应客户端 8.37（交接复查版，首包四个坑已修）
>
> **接手第一件事**：`MSYS_NO_PATHCONV=1 python _srv/pj_handoff_check.py`，27 项全 PASS 再动手。

---

## 0. 这是什么

一个 Windows 桌面工具（`破甲一键通`），给用户「一键给本地 AI 客户端打补丁」。
架构上是**空壳 exe + 云端核心**：exe 里不含业务逻辑，启动后用激活码换一份 Python 核心源码，在内存里 exec 执行。

```
exe（PyInstaller onefile，Cython 编译的 pyd）
  ↓ 启动
登录（激活码 → /pojia/auth 换 rt/at 令牌）
  ↓
拉核心（/pojia/fetch，HMAC 签名 + 封条校验）
  ↓
内存 exec 核心 → 得到 core 模块 → 驱动 UI
  ↓
用户勾目标 → 点破甲 → core.apply() 改本地文件
```

核心不在 exe 里，所以**改核心不需要重发客户端**，只有改 GUI 才要重新打包。

---

## 1. 目录结构

```
E:/DSH-Workspace/pojia-clean/
├── pj-824/                      ← 客户端源码（本地开发目录）
│   ├── pojia_gui.py             ← 主文件，1.3 万行，GUI + 云端握手 + HTTP 服务
│   ├── ui-test-836.spec         ← 正式包 PyInstaller 配置（console=False）
│   ├── ui-debug-836.spec        ← DEBUG 包（console=True）
│   ├── setup_pyd.py             ← Cython 编译配置（mingw32）
│   ├── _build_836.py            ← 构建脚本，`--debug` 切 spec
│   ├── ca.pem                   ← 客户端信任的自签 CA（CN=pojia-root-ca-2026）
│   ├── pojia_gui.pyd            ← 编译产物，5.3MB，别手改
│   ├── run_debug.bat            ← 给用户跑的调试启动器
│   └── dist/                    ← 打包输出
│
├── _srv/                        ← 服务端工具与配置源
│   ├── pjnew.py                 ← SSH 助手（core / hd 两台），**首选工具**（传文件走 base64，见 §9.9）
│   ├── pj_handoff_check.py      ← 交接体检：本地产物+服务端+版本闸+公网，27 项，退出码非 0 即有 FAIL
│   ├── test_zcode_apply.py      ← ZCode 目标端到端自测（假 .zcode → apply → revert，不碰真实配置）
│   ├── push_core_cos.py         ← 把 core.py 推到 COS（CDN 分发通道）并回读校验
│   ├── patch_anchor_accept.py   ← 给 _anchor_check 加过渡放行名单（一次性，已打）
│   ├── admin_live.html          ← 后台页面本地副本（改完上传）
│   ├── user_live.html           ← 领码页本地副本
│   ├── pj-ssl.conf              ← 主站 443 SNI 分流配置源
│   ├── pj-relay-https-standby.conf ← 高防 relay 配置源
│   └── patch_*.py               ← 历次服务端补丁脚本（可复用改法）
│
├── README.md                    ← 历史文档（8.20 时代的，部分过时）
├── 更新日志.md                   ← 版本变更记录
├── HANDOFF.md                   ← 本文件
└── 使用说明.md                   ← 面向用户的操作说明
```

**服务端真实路径**（在 `124.156.184.205`）：

```
/opt/pojia-cloud/
├── pojia_serve.py           ← 核心下发 + 鉴权 + 安全闸（跑在 127.0.0.1:8443）
├── pojia_code_web.py        ← 后台 + 领码 + 支付回调（127.0.0.1:8080）
├── pj_auth.py               ← 令牌签发（rt/at）
├── config.json              ← 总配置（payment / web_admin / maintenance / ops_mode）
├── version.json             ← 版本闸（min_ver / latest_ver / display_map / anchor_enforce）
├── keys/
│   ├── ca.crt               ← 自签 CA
│   ├── tls_server.pem       ← 服务端证书（CN=api.pojiaduan.cn）
│   ├── tls_server_key.pem
│   └── epay_priv.pem        ← 易付通 RSA 私钥
├── webui/
│   ├── admin.html           ← 后台页面（312KB，服务端注入红点）
│   ├── user.html            ← 领码页
│   └── site.html            ← 官网首页
├── dist/                    ← 安装包
│   ├── pojia-next-exe.zip   ← 软链，官网下载读这个
│   ├── pojia-next-v8.37-exe.zip
│   └── 破甲一键通GUI-8.37.exe
└── data/                    ← 全部运行时数据（见 MEMORY.md 第 4 节）
```

---

## 2. 客户端构建

### 2.1 正式包

```bash
cd E:/DSH-Workspace/pojia-clean/pj-824
"C:/Users/19294/AppData/Local/Programs/Python/Python312/python.exe" -u _build_836.py
```

三步：`cython --cplus -3 --no-docstrings` → `setup_pyd.py build_ext --compiler=mingw32` → `PyInstaller ui-test-836.spec --noconfirm`

产物：`dist/破甲一键通GUI-8.37.exe`，约 22.6 MB，冷启动 3–5 秒。

**构建脚本会自动做这些**（2026-11-08 加，别绕过它手动三步）：

```
[ver] pojia_gui.py  BUILD 8.37->8.37  DISPLAY 8.37->8.37   ← VER 是唯一真源，自动同步
[ver] ui-test-836.spec  VER=8.37
[py] 语法检查通过                                            ← 编译前先过语法，别等十分钟后炸
[pyd] 路径泄漏 {'C:/Users/19294': 0, ...}                   ← -ffile-prefix-map 验收
[exe] PYZ 模块 1234 个，可疑 []                              ← 混进 sitecustomize 直接判失败
[exe] 路径/宿主标记 0 命中
[done] dist\破甲一键通GUI-8.37.exe  23731315 B (22.6 MB)  sha256=...
```

改动 `VER` 就够，`BUILD_VER`/`DISPLAY_VER`/spec 名三处会跟着走 —— 手改会被覆盖，也
正是 8.37 首包「exe 叫 8.37、包里自报 8.36」的来源（后果：抬 `min_ver` 时强更死循环）。

### 2.2 DEBUG 包

```bash
python -u _build_836.py --debug
```

差异只有两处：`console=True`（带黑窗口）、exe 名带 `DEBUG`（触发 `_dbg()` 输出）。

控制台会打：

```
[HH:MM:SS][FETCH] 第 1/3 次  group=1121243020  code=PJ-xxxx  host=api.pojiaduan.cn:443
[HH:MM:SS][FETCH] 成功 486314 B  sha256=7a517a7f93f3743f
[HH:MM:SS][CORE] exec 云端核心 486314 B  sha256=7a517a7f93f3743f  CRLF=0 LF=9098
```

封条失败会跟完整 `traceback`，行号指向 `pojia_gui.py`。

**从工具会话里启动 GUI 会被一起收掉**（窗口站不同 + 进程随会话退出），所以
「启动后几秒进程没了」不等于包坏了。要看真实启动行为：在同一条命令里
`(./exe > run.log 2>&1 &) ; sleep 16 ; cat run.log`，能拿到 `[FETCH]/[CORE]` 就说明链路通；
窗口是否可见只能让人双击看。

### 2.3 改 GUI 的注意事项

- `pojia_gui.py` 单文件 1.3 万行，HTML/CSS/JS 全内嵌在 Python 字符串里
- 改页面用**脚本 + 精确锚点 + assert 计数**，别手改（容易撞重复锚点）
- 改完必须先 `py_compile` 再打包
- 新增网络调用要在 `.github/workflows/security.yml` 白名单里加函数名（bandit/semgrep 会拦）

---

## 3. 服务端部署

### 3.1 改 Python 文件

```bash
# 本地写补丁脚本（含 shutil.copy2 备份 + assert 计数）
# 上传
python _srv/pjnew.py core --put _srv/patch_xxx.py /tmp/patch_xxx.py
# 执行 + 校验 + 重启
python _srv/pjnew.py core "sed -i 's/\r$//' /tmp/patch_xxx.py && python3 /tmp/patch_xxx.py && python3 -m py_compile /opt/pojia-cloud/pojia_code_web.py && systemctl restart pojia-code-web && systemctl is-active pojia-code-web"
```

**必须**：`py_compile` 通过 + 服务 active + 打一次接口确认没挂。

### 3.2 改前端 HTML

`admin.html` 在服务器上，别直接 sed。流程：

```python
# 1. 拉下来
sftp.get('/opt/pojia-cloud/webui/admin.html', 'E:/.../_srv/admin_live.html')
# 2. 本地脚本改（读时 newline=''，先 replace('\r\n','\n') 统一）
# 3. 上传回去
sftp.put('E:/.../_srv/admin_live.html', '/opt/pojia-cloud/webui/admin.html')
# 4. 重启服务和刷新
```

`_admin_html()` 按 mtime 热加载，改完**不用重启**，但 `_sec_badge_html()` 注入走的是 `_admin_html()` 的返回值，重启更保险。

### 3.3 改 nginx

```bash
python _srv/pjnew.py core "cp /etc/nginx/sites-enabled/pj-ssl /etc/nginx/sites-enabled/pj-ssl.bak$(date +%s)"
# 改完
python _srv/pjnew.py core "nginx -t && systemctl reload nginx"
```

`nginx -t` 不过**绝对不要 reload**，否则 nginx 起不来全站挂。

### 3.4 换核心（core.py）—— 三步，少一步就有客户端报 SIG

核心不走 exe，改一次影响所有在线客户端，流程必须按顺序：

```bash
# 1) 传新核心（本地改完必须先用 _云端加密/seal_repack_836.py 重封条，否则客户端拒启 exit 3）
MSYS_NO_PATHCONV=1 python _srv/pjnew.py core --put 破甲一键通.py /opt/pojia-cloud/core.py

# 2) 同步 CDN 对象 —— 客户端带 cdn=1 时二进制是从 COS 拉的，
#    只换 core.py 不换对象 → 客户端哈希对不上报「SIG 安全校验失败」，
#    而服务端日志里还是 ok:1，光看日志查不出来
MSYS_NO_PATHCONV=1 python _srv/pjnew.py core "cd /opt/pojia-cloud && python3 /tmp/push_core_cos.py"

# 3) 用 DEBUG 包实测一遍
#    期望：[FETCH] 成功 <新大小> B sha256=<新前16位> → [CORE] exec ... 无 traceback
```

**换核心前先开过渡放行**，否则手里有缓存的老客户端（8.36 及更早，没有自愈逻辑）
全部 `core_mismatch` 403：

```bash
python3 - <<'PY'
import json
p='/opt/pojia-cloud/version.json'
d=json.load(open(p)); d['anchor_accept_sha']=[旧核心sha256]; json.dump(d,open(p,'w'),ensure_ascii=False,indent=2)
PY
```

`_anchor_check` 会认这个数组，放行同时写 `data/anchor_accept.jsonl`。
观察 3~7 天、确认 `cdn_fetch.jsonl` 里 `core_sha` 全变成新值后，把这个数组清空。

`_load_core()` 按 mtime 热加载，换 core.py **不用重启** pojia-cloud。
`pojia_serve.py` 改动则必须 `python3 -m py_compile` + `systemctl restart pojia-cloud`。

---

## 4. 一次完整的数据流

```
1. 用户领码
   浏览器 → https://pojiaduan.cn/codeweb/
   POST /api/lic/start {qq, pw}
     - 免费模式（ops_mode=free）：直接建 paid 订单，返回 already=1（已有码）或成功
     - 付费模式：建 pending_pay 订单，返回支付宝链接
   POST /api/lic/code {qq, pw} → 返回 code（PJ-XXXX-XXXX-XXXX）

2. 用户登录客户端
   填激活码 → POST /pojia/fetch {hwid, group, code, nonce, ts}
     - 服务端校验：黑名单 → 群封禁 → 限流 → 激活码有效 → hwid 绑定 → HMAC
     - 通过后下发 core（485KB，压缩后的 Python 源码）
     - 同时签发 rt/at 令牌（写 cloud.json）

3. 客户端加载核心
   _core_module_from(src) → exec(compile(src, "<pojia-cloud>"))
     - 核心内部做封条校验（self_seal），失败抛异常
     - 成功后设置 _CORE_READY，UI 状态变 ready

4. 用户点破甲
   勾目标 → POST /api/action {action: "apply", targets: ["dsh"]}
     - 核心 ready 才执行；未 ready 则排队（_PENDING_ACT）
     - 执行 _run_action_async → core.apply() → 改本地文件
     - 结果推回 /api/state，卡片状态变「已注入」
```

---

## 5. 接口清单

### 客户端本地 HTTP（端口随机，`netstat` 找）

| 路径 | 说明 |
|---|---|
| `/api/state` | 主状态（targets / core_file / core_load / stats） |
| `/api/cloud/state` | 云端验证状态（state / offline / account / saved_code） |
| `/api/cloud/verify` | 提交激活码登录 `{group, code, remember}` |
| `/api/core_status` | 核心加载状态（ready / state / msg / elapsed） |
| `/api/action` | 执行动作 `{action, targets}` |
| `/api/groups` | 群列表（内置，不联网） |
| `/api/account` | 头像昵称 |

### 服务端（443 → 8443）

| 路径 | 说明 |
|---|---|
| `/pojia/fetch` | 核心下发（HMAC 签名） |
| `/pojia/auth` | 令牌 `op=login/refresh` |
| `/pojia/version` | 版本闸（min_ver / display_ver） |
| `/pojia/notice` `/pojia/ads` `/pojia/groups` | 公告/广告/群列表 |

### 后台（8080）

| 路径 | 说明 |
|---|---|
| `/api/admin/login` | `{u, p, t}` 三字段 |
| `/api/admin/data` | 数据看板（users / stats / total_users） |
| `/api/admin/mode` | 运营模式 `act=save&mode=free\|paid` |
| `/api/admin/sec` | 安全中心 `act=stats\|list\|ban\|unban\|audit\|wlist\|wadd\|wdel` |
| `/api/admin/paycfg` | 支付配置 |
| `/api/admin/groups` | 群管理 `act=refresh` |
| `/api/admin/words` | 防炸群词表 |

### 领码（8080，走 /codeweb/）

| 路径 | 说明 |
|---|---|
| `/api/lic/start` | 下单（免费模式直接 paid） |
| `/api/lic/code` | 取码 |
| `/api/pay/notify` | 易付通回调（**GET**，不是 POST） |
| `/api/reg` | 官网注册领码 |

---

## 6. 排错决策树

**客户端「核心下载失败」**

```
1. 让用户跑 DEBUG 包，看控制台 [FETCH] 那行
2. 失败码是 BADCODE/USEDCODE → 激活码无效，不是技术问题
3. 失败码是 NET → 网络层，让关代理/VPN
4. 失败码是 core_mismatch → 本地缓存脏，客户端会自动清缓存重拉
5. 成功但那行 [CORE] 后面有 traceback → 封条校验失败，看行号定位核心源码
6. 都没有 → 服务端日志 data/cdn_fetch.jsonl 查这个 hwid 有没有 ok:1
```

**客户端「本机用户」**

```
1. 说明账号 API 没拿到数据
2. 查 /api/cloud/state 返回的 account 是否为 null
3. 查 cloud.json 里有没有 rt
4. 没有 → 重新登录；有 → 服务端 /api/avatar 返回什么
```

**官网打不开**

```
1. 先确认 DNS：nslookup pojiaduan.cn 8.8.8.8 应为 119.28.44.49
2. 还是 124 → DNSPod 改错了或 TTL 没过
3. 已是 119 但打不开 → 高防机 nginx：systemctl is-active nginx
4. 高防正常但 502 → 高防到主站不通：ssh hd "curl -I https://124.156.184.205"
5. 主站 nginx 挂 → ssh core "nginx -t && systemctl status nginx"
```

**后台 403**

```
1. 先看是不是 IP 白名单（老板换 IP 了）
2. 加 allow 后 reload：nginx -s reload
3. 还是 403 → TOTP 时间不同步，用 admin_token 走接口
```

---

## 7. 危险操作与回滚

| 操作 | 危险点 | 回滚 |
|---|---|---|
| 改主站安全组 | 只留高防 IP，DNS 没切就全站挂 | 恢复 `0.0.0.0/0` |
| 改 `anchor_enforce=true` | 老客户端缓存核心对不上会被拒 | 改回 false 或让客户端清缓存 |
| 改 `min_ver` | 低于此版本的客户端全部 426 | 改回低值 |
| 改高防 443 证书 | 客户端 ca.pem 固定校验，换证书=全量失联 | 换回 `keys/tls_server.pem` 原件 |
| 删 `security.json` | 黑名单清空，被封的自动解封 | 无 |
| `systemctl restart pojia-cloud` | 重启期间 3–5 秒不可用 | 自动恢复 |

所有 Python 补丁脚本都自带 `shutil.copy2(P, P + ".bakxxx" + timestamp)`，回滚就是 `cp` 回去。

---

## 8. 常用命令速查

```bash
# SSH
python _srv/pjnew.py core "命令"
python _srv/pjnew.py hd "命令"

# 服务状态
python _srv/pjnew.py core "systemctl is-active pojia-cloud pojia-code-web nginx"

# 看实时日志
python _srv/pjnew.py core "journalctl -u pojia-cloud -n 50 --no-pager"

# 强制刷新高防缓存
python _srv/pjnew.py hd "rm -rf /var/cache/nginx/pj/* && systemctl reload nginx"

# 查某个 hwid 的拉取记录
python _srv/pjnew.py core "grep 你的hwid /opt/pojia-cloud/data/cdn_fetch.jsonl | tail -5"

# 查支付回调
python _srv/pjnew.py core "tail -5 /opt/pojia-cloud/data/epay_notify.log"

# 查黑名单
python _srv/pjnew.py core "cat /opt/pojia-cloud/data/security.json | head -40"

# 证书到期
python _srv/pjnew.py core "openssl x509 -in /etc/letsencrypt/live/pojiaduan/fullchain.pem -noout -dates"
```

---

## 9. 给下一个 AI 的提醒

1. **先跑体检，别先猜**：`MSYS_NO_PATHCONV=1 python _srv/pj_handoff_check.py` —— 27 项覆盖本地产物 / 服务端单元 / 版本闸 / 公网链路，FAIL 是真问题，WARN 看备注。
2. **本机 curl 测域名必被代理污染**（`Tunnel connection failed: 502`）。测公网一律在服务器上测，或用体检脚本里「服务器侧」那一组。
3. **改大文件用脚本**。`admin.html` 312KB，手改必出错。
4. **每次改完必须验证**：`py_compile` + 服务 active + 打一次接口。
5. **备份是默认动作**。所有补丁脚本第一行就是 `shutil.copy2`。
6. **老板的 IP 是 `117.136.49.2`**，后台和 9443 白名单只认这个。他换 IP 会锁死。
7. **交付物给 sha256**，放 `E:/桌面/破甲/<版本>/`。
8. **`MEMORY.md` 有 3000 字符写入限制**，日常只追加当天日志，长期事实才改它。
9. **`pjnew.py` 传文件别再写 `sftp.put`**：主站 SFTP 和 shell 不在同一文件系统视图（put 报成功、shell 看不到、get 直接 ENOENT）。已改成底层 channel 分块 base64，直接用 `--put/--get`。
10. **Git Bash 会把 `/tmp/x` 转成 `C:/Users/.../Temp/x`**：给远端命令传绝对路径时前面加 `MSYS_NO_PATHCONV=1`，否则文件写到远端一个叫 `C:/...` 的目录里，`ls /tmp` 永远找不到。
11. **版本号只有一个真源**：`pj-824/_build_836.py` 顶部的 `VER`。构建时自动同步 `BUILD_VER`/`DISPLAY_VER`/两个 spec；手改那三处会被下次构建覆盖。首包就是因为 `BUILD_VER` 没抬，埋了「强更死循环」的雷。
12. **构建自检已内置**：出包后自动解 PYZ，混进 `sitecustomize`/`usercustomize` 直接判失败（构建机 WorkBuddy 的 safe-delete shim 会污染，症状是客户端所有删除变成「移进回收站」）；pyd 里残留构建机路径也判失败。
13. **核心有整文件封条**：直接改 `破甲一键通.py` 必然拒启（exit 3）。改完跑 `_云端加密/seal_repack_836.py`，基线用**改动前**的副本：`POJIA_SEAL_OLD=<改动前的 core.py>`，它会回填 `_PYD_SHA256` 并自检本地/云注入/二改拒启三种模式。
14. **换核心三步别省**（传 core.py → `push_core_cos.py` 同步 CDN → DEBUG 包实测），并先开 `anchor_accept_sha` 过渡放行。细节见 §3.4。
15. **8.37 首包的四个坑已修**，逐条见 `更新日志.md` 的「8.37 补记」：BUILD_VER 错配 / PYZ 混 shim / ZCode `_mirror_block` 缺失 / 换核心没同步 CDN。
16. **下架旧版本是四处联动**：`version.json` 的 `min_ver` + `url`、服务端 `dist/` 旧包、GitHub Releases（建新版设 Latest / 删旧 release）、高防缓存。只抬 `min_ver` 而 `url` 和 GitHub 还指旧包，被强更的用户会下载回旧版，无限循环 —— 8.37 发布前 GitHub Latest 是 **v8.34**、仓库里连 8.37 都没有，就是这个坑。九步流程见 `发版清单.md`，一键脚本 `_srv/release_837.py`（幂等）。
17. **8443 是 TLS**：`journalctl -u pojia-cloud` 里写 `listening on 0.0.0.0:8443 cert=tls_server.pem`。验证接口别用 `http://127.0.0.1:8443/...`（curl rc=56），用 `curl -sk --resolve api.pojiaduan.cn:443:127.0.0.1 https://api.pojiaduan.cn/...`，跟客户端真实链路一致。
18. **本机 Python 的 `sitecustomize` 会把删除改成「移进回收站」**（`shutil.rmtree.__module__ == 'sitecustomize'`）。清理 / 发版脚本要么用 `python -S`，要么照 `_srv/pj_cleanup.py` 自检后用 `-S` 重启自己，否则 `disk_usage` 一点没变，文件全躺在 `E:\$RECYCLE.BIN`。
19. **免费模式只免领卡**：`config.json` 的 `ops_mode=free` 只在 `pojia_code_web.py:5189`（下单金额）和 `:5256`（支付闸）生效，解绑 / 多设备开通仍按原价。改官网活动文案别写「全部免费」，会跟领码页对不上。
20. **2026-11-08 限时免费一天**：官网公告由前端按 `2026-11-09T00:00:00+08:00` 自动切回收费版（同时读 `/api/paycfg` 校准），后端由 `/etc/cron.d/pojia-free-end` 在 0 点跑 `/opt/pojia-site/restore_paid.py` 把 `ops_mode` 改回 `paid`，脚本跑完自删 cron。**查「为什么突然收费了」先看 `/var/log/pojia-free-end.log`**；想取消自动恢复就删那个 cron 文件。
21. **容量基线（2026-11-08 实测）**：高防近 1h ≈9 QPS / 峰值分钟 ≈21 QPS，主站 ≈7.6 QPS；两台机 load < 0.3、内存余量 6.5G / 1.4G。核心 TLS 压测 380 QPS、领码 894 QPS（@50 并发 p95 60ms）—— 应用层有 40–100 倍余量，**免费活动 + 强更下架带来的验证/领卡流量压不垮**。查容量跑 `python _srv/capacity.py check --stress`。
22. **真正的瓶颈是 23 MB 下载包，不是 CPU**：高防公网出口实测 13–18 Mbps（腾讯云香港实例带宽档），单路下载 10 秒，并发 3/6 路总吞吐不增反降（38.9s / 77.4s）。全天理论 160 GB ≈ 7000 次下载，分摊一天没问题；瞬时 100 人同时下载要排队约 20 分钟。要根治得把 exe/zip 分流到 COS/CDN 或在控制台提公网带宽，光加 CPU / 加 nginx worker 没用。
23. **nginx 默认配置是隐藏瓶颈**：Ubuntu 默认 `worker_connections 768` 且 worker `nofile=1024`（每连接吃 2 个 fd，实际并发上限约 500/worker）；`pojia_code_web.py` 的 `ThreadingHTTPServer` 默认 `listen backlog=5`，50 并发时 p95 1.44 秒。已用 `_srv/capacity.py tune` / `tune-web` 改成 4096 / 65535 / backlog 128，`nginx -t` 通过才 reload，备份 `*.bak-cap-20261108-*`，回滚 `python _srv/capacity.py tune --rollback`。另：reload 后旧 worker 带着旧 limits 慢慢退，巡检统计 nofile 时**必须排除 `shutting down`**，否则误报 1024。
24. **高防的 429 先看来源 IP 再判断**：`pj-relay-site.log` 里每小时几百个 429 基本都是 GCP 扫描器扫 `/.env`（`34.64.70.221` / `35.237.8.234`），不是用户被限。`pjrelay 120r/m` 只管普通路径，`/dist/` 和只读接口已迁到 `pjstatic 900r/m`，避免分片下载被自己限流打断。
