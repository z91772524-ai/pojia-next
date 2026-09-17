# 破甲一键通 v6.0

把桌面那**几套**桌面端 AI 客户端"破甲"工具，合并成**一个脚本**：一套人格，两个目标，**零第三方依赖**（纯 Python 标准库）。

> 原工具目录一个字节都没动。本目录可独立使用，也可以整包发给别人。

合并来源：`WorkBuddy_Unlock_一键破甲_v1`、`WorkBuddy破甲-v4`、`workbuddy国际版本破甲`、`dsh-purge`。

---

## 一、管哪两个目标

| 目标 | 是什么 | 注入方式 |
|---|---|---|
| `dsh` | DeepSeek Harness（桌面端 / npm 全局 / npx 缓存 / 便携版） | 三层文件级补丁：提示词层、persona 层、区段层 |
| `wb` | WorkBuddy | 六层靶点：模板 / `product.json` / 命令闸门 / 网页过滤 / 运行时缓存 / 会话快照 |

---

## 二、快速开始

### 最省事：双击

双击 **`一键破甲.bat`** → 出菜单 → 按数字选：

```
  [1] 一键破甲         DSH + WorkBuddy 全打一遍
  [2] 检测状态         只读，不改任何文件      ← 建议先看这个
  [3] 诊断详情         逐文件列出补丁/备份状态
  [4] 预演             只显示会改什么
  [5] 选目标单打        dsh / wb 任选
  [6] 还原              选择目标还原成官方原版
  [7] WorkBuddy 守护    安装 / 卸载 / 查看后台守护任务
  [8] WorkBuddy 快照    生成基准 / 与基准对比
  [0] 退出
```

### 命令行

```bash
python 破甲一键通.py                            # 交互菜单
python 破甲一键通.py --status                   # 只读：三个目标全查一遍
python 破甲一键通.py --diagnose                 # 只读：详细取证
python 破甲一键通.py --dry-run                  # 预演，不改盘
python 破甲一键通.py --apply --yes              # 真打（自动跳过没装的）
python 破甲一键通.py --apply --target wb --full --yes   # 只打 WorkBuddy 的完全破甲
python 破甲一键通.py --revert --target dsh --yes        # 只还原 DSH
python 破甲一键通.py --apply --persona 我的.md --force --yes
python 破甲一键通.py --pick dsh                 # 手动指定安装目录（弹系统目录窗口）
python 破甲一键通.py --guard install            # 装 WorkBuddy 守护任务
```

常用开关：

| 开关 | 作用 |
|---|---|
| `--target all\|dsh\|wb` | 选目标，可逗号分隔（默认 `all`） |
| `--full` | WorkBuddy 完全破甲：+网页过滤 +Ask 模式 +文件保护中和 |
| `--force` | 已破甲的目标也重写（用于把两套统一成同一份人格） |
| `--pick TARGET` / `--clear` | 手动指定安装位置并记住 / 清除记住的路径 |
| `--kill-dsh` | 允许结束正在跑的 DSH 进程（**默认禁止**，见下） |
| `--yes` / `-y` | 非交互，不二次确认 |

**找不到安装位置**时，脚本会自动扫 `%LOCALAPPDATA%\Programs`、`Program Files`、注册表、**所有盘符**、正在运行的进程、npm 全局目录、npx 缓存。还找不到的话，它会弹一个二选一：

- 输 **A** → 用默认浏览器打开下载页（DSH → 社区桌面版；WorkBuddy → 官网 workbuddy.cn），装好重跑即可
- 输 **B** → 弹出系统目录选择窗口手动指定，**选完会记住**，下次不用再选

命令行同样可以：`python 破甲一键通.py --pick dsh`（或 `wb` / `all`），想改回自动探测加 `--clear`。

---

## 三、它到底改了什么

- **DSH**：把 `WORKSPACE_CONTEXT_INTRO` 一类"仅供参考、不覆盖系统指令"的免责声明升级成"ACTIVE 且强制"；剥离官方默认身份，改由 `persona.md` 作唯一身份来源。
- **WorkBuddy**：六层靶点 —— ① `templates\*.tpl` 政策块整块替换；② `cli\product.json` 内嵌提示词文本级替换（不重排 JSON）；③ `codebuddy.js` 命令闸门解锁 + 去网页内容过滤；④ 数据目录 `plugins` 里的副本；⑤ `cache\acc-product-config-v3.json` 运行时缓存；⑥ `TEMP` 会话快照（默认只清 24 小时以上的）。

---

## 四、人格怎么改

改同目录的 **`persona.md`**，脚本会把它拼在内置强化版内容政策**前面**，两个客户端收到完全一致的口径。改完生效：

```bash
python 破甲一键通.py --apply --force --yes
```

优先级：`--persona 文件` > `persona.md` > `my-prompt.txt` > 内置默认。

> 为什么要 `--force`：脚本默认"已经破甲过就不重复写"。WorkBuddy 的 `product.json` 有 613KB、`codebuddy.js` 有 23MB，白写一遍没意义。只有主动改了人格时才需要。

---

## 五、安全 & 可逆

- **改前必留备份**，后缀跟原工具保持一致，可互相还原：DSH → `<文件名>.dshpurge.bak`；WorkBuddy → `<文件名>.unlockbak`。另按时间戳归档一份到 `历史备份/`。
- **升级自愈**：官方升级覆盖文件后，能识别"当前是干净官方版、备份是更老原版"，自动归档旧备份重建基准，不会出现"还原一下反而把文件降级"。
- `--revert` / `--restore` 随时还原。只做文件级补丁，**不删包、不碰注册表/服务**。
- `--status` / `--dry-run` 纯只读，可以先看再动手。

---

## 六、关于 DSH 进程（重要）

**脚本默认绝不会结束正在跑的 DSH 进程。**

DSH Desktop 的进程里很可能就跑着正在跟你对话的那个会话 —— 杀它等于自杀，还会丢未保存的对话。

- 检测到 DSH 在跑 → 提示一下，然后**继续打补丁**（改的是磁盘文件，不影响当前进程）；
- 改动要**重启 DSH** 才生效；
- 确实想结束进程，才加 `--kill-dsh`。

---

## 七、WorkBuddy 守护任务

`--guard install` 会装两个计划任务，防止补丁被官方升级/自检冲掉：`WorkBuddyUnlockV6_Hourly`（每 30 分钟）、`WorkBuddyUnlockV6_Logon`（每次登录，需管理员）。守护进程用 `pythonw.exe` 调 `--quiet`，没有黑框闪现。

---

## 八、常见问答

**Q：跑完要重启吗？** —— 要。DSH 和 WorkBuddy 需完全退出（含托盘）再打开。

**Q：官方升级后补丁还在吗？** —— 升级会覆盖 `node_modules` / `resources`，补丁被冲掉，重跑 `--apply` 即可（会自动识别哪些被冲掉，只补该补的）。

**Q：怎么知道补丁有没有被冲掉？** —— `python 破甲一键通.py --status`；WorkBuddy 还可 `--snapshot` 留基准、`--compare` 对比。

---

## 文件说明

| 文件 | 说明 |
|---|---|
| `破甲一键通.py` | 主程序，约 142KB，纯标准库 |
| `一键破甲.bat` | 纯 ASCII 启动器，通配符定位 `.py`，自动找 Python |
| `persona.md` | 唯一共用人格源 |
| `使用说明.md` | 完整说明书（228 行） |
| `修复报告.md` | 相比原工具修掉的 18 处缺陷（B1–B18）+ 3 处合并层问题（C1–C3），逐条对照 |
| `赞赏码.png` | 微信支付 / 支付宝收款码（自愿打赏用，不参与功能） |
| `LICENSE` | MIT 许可证 |
| `.gitattributes` | 仓库内统一 LF，但 `.bat` 强制 CRLF（否则 clone 下来双击失效） |
| `.gitignore` | 排除 `状态/`、`破甲日志.txt` 等运行时产物 |

---

## 免责声明

**先说清楚：这个工具不含任何病毒、木马、后门或挖矿程序，不联网、不上传任何数据。**

- **全部是纯文本**：一个 Python 文件（约 142KB）、一个批处理启动器、一份人格文件、三份 Markdown 文档。没有编译产物、没有二进制、没有加密壳，用记事本就能逐行读完。
- **不联网**：脚本全程只在本机读写文件，不发送任何网络请求，不收集设备信息、账号信息或使用数据（断网也能跑，功能一样）。
- **只做文件级补丁**：只改写目标客户端的提示词/配置文件；**每个改动都先备份**；不删包、不碰注册表/服务、不装驱动、不常驻后台（守护计划任务是可选的，跑 `--guard install` 才装）。
- **随时可还原**：`--revert` 一键回到官方原版。
- **你可以自己验证**：建议第一次先跑 `--status`（纯只读，什么都不改）、再跑 `--dry-run`（只显示会改什么）；不放心就把 `破甲一键通.py` 全文读一遍，或断网运行。
- **风险自担**：本工具会修改第三方客户端的本地文件，可能导致其行为变化，也可能与官方服务条款相冲突。用不用、怎么用，由使用者自行判断并承担后果。
- **完全免费**：任何人向你收钱都不是作者行为（下方赞赏码纯属自愿）。

---

## 共同创作 / Credits

本项目的代码、文档与发布流程，由作者借助 **DeepSeek Harness** 与 **WorkBuddy** 协作完成：

| 协作方 | 官方网站 | 在本项目里的角色 |
|---|---|---|
| **DeepSeek Harness（DSH）**<br><sub>v2.0.10</sub> | [github.com/anywhere-labs/dsh-desktop](https://github.com/anywhere-labs/dsh-desktop) | 主要开发环境：五套工具合并、18 处缺陷排查与修复、文档撰写、发布流程 |
| **WorkBuddy**（腾讯）<br><sub>v5.5.6</sub> | [workbuddy.cn](https://www.workbuddy.cn) | 目标客户端之一；本项目前身「WorkBuddy 系列破甲工具」的提示词与逻辑来自其生态 |
| **作者** | [@z91772524-ai](https://github.com/z91772524-ai) | 需求提出、实机验证、最终把关 |

> **关于 GitHub 上怎么署名的（重要）**：本项目在提交信息里用 `Co-authored-by` 标注了 DeepSeek Harness 与 WorkBuddy，**提交页面可以看到这两位共同作者**。
>
> 但 **GitHub 的 Contributors（贡献者）列表只统计「个人账号」**：组织账号（如 `anywhere-labs`）和没有 GitHub 账号的产品，无论怎么写都不会出现在那个列表里——作者实测验证过（组织的 noreply 邮箱两种写法都不被解析）。所以它们的署名以本节表格 + 提交信息为准，**不是漏掉了**。

---

## 交流 & 支持

- **QQ 交流群：`1121243020`** —— 使用问题、更新通知、新版本都发在群里，有问题直接来问
- **Telegram 交流群：[t.me/shendusikao666](https://t.me/shendusikao666)** —— 墙外 / 海外的朋友走这边（群名「深度思考」）
- 有 bug 或想法，也可以在本仓库提 [Issue](https://github.com/z91772524-ai/pojia-next/issues)

如果这个脚本帮到了你，可以请我喝杯奶茶 —— **不打赏是本分，打赏是对我的认可**：

![赞赏码](赞赏码.png)

<sub>微信、支付宝都能扫。完全自愿，不打赏也照样用。</sub>

---

## 许可证

**MIT License** —— 随便用、随便改、随便分发、甚至可以商用，保留版权声明即可。详见 [LICENSE](LICENSE)。

---

*仅供本地自用与学习研究。整个文件夹打包就能发给朋友，脚本自己找 Python、自己找客户端安装位置。完全免费，别花钱买。*
