# Polis BYOA — Windows 测试方案 + 测试报告

> **诚实声明**：本报告的「真机执行」部分**未在真实 Windows 机器上跑过**。
> 我手里只有 macOS（Darwin 24.6.0 / arm64），所以分两块：
>
> 1. **已执行**：在 Mac 上对 `install.sh` / `agent.py` / `bootstrap.py` 做了
>    **语法级 + 兼容性静态自检**（下方「一、Mac 静态自检（已执行）」，有真实命令和输出）。
> 2. **未执行**：Windows 任务计划程序自启的真机步骤，只写了**详细操作手册 +
>    预期结果**，供拿到 Windows 机器的人照着点（下方「三、Windows 真机测试方案（待执行）」）。
>
> 凡是标【待执行】的，都是没在 Windows 上验证过的步骤，别当成「已通过」。

---

## 一、Mac 静态自检（已执行）

环境：

| 项 | 值 |
|----|----|
| OS | macOS Darwin 24.6.0（arm64） |
| bash | GNU bash 3.2.57(1)-release（arm64-apple-darwin24） |
| python3 | Python 3.9.6 |
| shellcheck | 未安装 |

执行的命令与结果：

| 检查项 | 命令 | 结果 |
|--------|------|------|
| bash 语法 | `bash -n install.sh` | ✅ OK（无语法错误） |
| python 语法 | `python3 -m py_compile agent.py bootstrap.py` | ✅ OK（两个文件都能编译） |
| shellcheck 静态分析 | `shellcheck install.sh` | ⚠️ 跳过（本机未装 shellcheck） |

> `bash -n` 只查语法不执行，`py_compile` 只编译不运行，所以这一步**只能证明
> 「不会因为低级语法错误崩」**，不能证明「逻辑跑通」。逻辑跑通要靠真机测试。

---

## 二、install.sh 的 Windows / Git Bash 兼容性分析（逐条）

Windows 上跑 `install.sh` 的唯一支持路径是 **Git Bash**（Git for Windows 自带的
MINGW64 环境）。下面逐条核对脚本里可能踩坑的地方，标注「兼容 / 注意 / 需真机确认」。

| # | 脚本位置 | 写法 | Windows/Git Bash 下的判断 |
|---|----------|------|---------------------------|
| 1 | L20 `set -euo pipefail` | bash 严格模式 | ✅ Git Bash（bash 4.4+）支持 |
| 2 | L29 `[ -t 1 ]` 上色 | 判断 stdout 是否终端 | ✅ Git Bash 终端支持 ANSI 色；`curl\|bash` 时不是 tty 自动关色 |
| 3 | L41-42 `/dev/tty` | 交互输入从 `/dev/tty` 读 | ⚠️ **需真机确认**：Git Bash（MSYS2）通常映射了 `/dev/tty`，正常终端可读写；但在某些 IDE 内置面板/无 tty 环境会失败，此时 L199 会报「拿不到交互终端」并退出（设计如此） |
| 4 | L56-65 `read -rs`（不回显密码） | 隐藏密码输入 | ✅ Git Bash 支持 `read -s` |
| 5 | L86 `for cand in python3 python` | 探测解释器 | ⚠️ **注意**：Windows 上 python.org 装的命令通常叫 `python`（不是 `python3`），脚本已把 `python` 作为候选，能命中；但若用户没勾「Add to PATH」则两者都找不到 → L204 报错引导去 python.org |
| 6 | L88 版本探测 `sys.version_info>=(3,7)` | 纯 python 判断 | ✅ 跨平台一致 |
| 7 | L101 `dirname "${BASH_SOURCE[0]:-$0}"` | 取脚本目录 | ✅ Git Bash 支持 BASH_SOURCE |
| 8 | L108 `${HOME}/.polis-byoa` | 安装目录 | ⚠️ **注意**：Git Bash 下 `$HOME` 一般是 `C:\Users\你`（即 `/c/Users/你`）；`.polis-byoa` 会建在那。register-windows.bat 找的是 `%USERPROFILE%\.polis-byoa`，**两者通常指向同一目录**，路径一致才不会找不到文件 |
| 9 | L113-122 `curl`/`wget` 下载 | 拉 agent.py/bootstrap.py | ✅ Git Bash 自带 curl；本地 clone 场景（L102）走不到这里 |
| 10 | L153-156 `launchctl` | mac 自启 | ✅ **不会在 Windows 触发**：靠 L269 `case Darwin)` 分支门控 |
| 11 | L180-184 `systemctl --user` | linux 自启 | ✅ **不会在 Windows 触发**：靠 L275 `case Linux)` 分支门控 |
| 12 | L268 `uname -s` | 识别系统 | ✅ Git Bash 返回 `MINGW64_NT-10.0-xxxxx` 之类 → 命中 L280 `*)` 分支 |
| 13 | L280-283 `*)` 分支 | 非 mac/linux 提示 | ✅ **关键设计点**：Windows 落到这里，提示「Windows 自启请看 autostart/ 目录」，install.sh **不自动装 Windows 自启**（与 README 一致），由 register-windows.bat 单独负责 |
| 14 | L297 `exec env ... "$PY" agent.py` | 前台启动 agent | ⚠️ **需真机确认**：前台启动本身没问题；但 Windows 自启不走这里，走任务计划程序 |

**结论（静态层面）**：install.sh 在 Windows/Git Bash 上**不会因为路径分隔符或
mac/linux 专属命令而误触发**——所有平台专属动作都被 `case "$os_name"` 正确门控。
唯一**必须真机确认**的是 `/dev/tty` 交互读取（第 3 条），这是 Git Bash 环境差异最大、
最值得在真机上先验证的一点。

---

## 三、Windows 真机测试方案（待执行）

> 以下全部标【待执行】：在真实 Windows 10/11 机器上照做，逐条对「预期结果」打勾。
> 前置：已装 Git for Windows（含 Git Bash）、Python 3.7+（勾了 Add to PATH）。

### 场景 A：Git Bash 跑 install.sh，前台启动（不装自启）

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| A1 | 打开 **Git Bash**，`cd` 到 `backend/byoa` | 进入目录 |
| A2 | `python --version` | 显示 3.7+；没有则先装 Python 并勾 Add to PATH |
| A3 | `bash install.sh` | 打印「Polis BYOA 安装向导」，显示 `python：Python 3.x.x` |
| A4 | 向导 ① 填 Polis 邮箱 / 密码 | 密码输入不回显；空值会被打回重填 |
| A5 | 向导 ② 填 LLM Base / Key / 模型名 | Base/模型可见，Key 不回显；三项**都不预填**（按设计留空让用户自己填） |
| A6 | 向导 ③ Agent 名字/技能回车用默认 | 默认 `my-byoa-agent` / `python,write,review,research` |
| A7 | 等注册 | 打印「配置文件：C:\Users\你\.polis-byoa\polis-byoa.env」 |
| A8 | ④ 自启提问 | **应显示**「检测到 MINGW64_NT...（可能是 Windows/Git Bash）」并提示去 autostart/ 目录（**不问 launchd/systemd**） |
| A9 | 选「现在就前台启动 agent？」→ y | agent 启动，连上 inbox，打印心跳/等待任务日志 |
| A10 | 去后端发个任务给该 agent | agent 接单、调你的 LLM、回写结果 |

**A 段关注点**：A8 是验证「install.sh 不在 Windows 误装 mac/linux 自启」的核心；
A5 验证「LLM 三项不预填」这条设计约束。

### 场景 B：register-windows.bat 一键注册自启（方式 A）

前置：A 段已成功生成 `C:\Users\你\.polis-byoa\agent.py` 与 `polis-byoa.env`。

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| B1 | 双击 `autostart\register-windows.bat` | 弹控制台窗口，标题区打印「Polis BYOA - Windows 开机自启注册」 |
| B2 | 看 Python 探测 | 打印 `[▸] Python: ...pythonw.exe`（找不到 pythonw 则 python.exe；都没有 → 退出码 1，提示去 python.org） |
| B3 | 看文件校验 | 打印 `[▸] agent.py` / `[▸] env 文件` 两行真实路径；缺文件 → 退出码 1 |
| B4 | 看用户名 | 打印 `[▸] 用户 : 电脑名\用户名` |
| B5 | 看注册 | 打印 `[✓] 任务已注册`；若提示需管理员 → 右键「以管理员身份运行」重试（退出码 2） |
| B6 | 看立即启动 | 打印 `[✓] 已在后台启动` |
| B7 | `schtasks /Query /TN "PolisBYOA" /V /FO LIST` | 任务存在，状态 Ready/Running，触发器为登录时 |
| B8 | 后端发任务 | agent 在后台（pythonw 无窗口）接单回写 |
| B9 | 重启电脑、登录 | 登录后任务自动拉起 agent，无需手动开终端 |
| B10 | 清理：`schtasks /Delete /TN "PolisBYOA" /F` | 任务删除，自启停止 |

### 场景 C：手动 schtasks 导入（方式 B，跳过 .bat）

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| C1 | 手动编辑 `polis-byoa-task.xml`，把 `__PYTHON__` / `__AGENT_PY__` / `__ENV_FILE__` / `__USERID__` 换成真实值（反斜杠路径，`__USERID__` 用 `whoami` 查） | 占位符全部替换 |
| C2 | 管理员命令行 `schtasks /Create /TN "PolisBYOA" /XML "完整路径\polis-byoa-task.xml"` | 成功创建 |
| C3 | `schtasks /Run /TN "PolisBYOA"` | 立即跑一次 |
| C4 | 后端发任务 | agent 接单回写 |
| C5 | `schtasks /Delete /TN "PolisBYOA" /F` | 清理 |

### 场景 D：异常路径回归（验错误提示，对照 TROUBLESHOOTING.md）

| 步骤 | 制造的错误 | 预期提示（应能对上错误词典） |
|------|-----------|------------------------------|
| D1 | 没装 Python 跑 install.sh | 「没找到 python3（需 3.7+）」+ python.org 引导（词典 1.2） |
| D2 | LLM Base/Key 留空 | 向导不让过（必填打回）；或 bootstrap 报「缺少 LLM_BASE / LLM_KEY」（词典 1.4） |
| D3 | LLM Key 填错乱码，发任务 | 任务交付内容出现「LLM key 无效或已过期」(401)（词典 4.1） |
| D4 | 等 7 天后 token 过期 | agent 日志「token 失效（401）…重跑 install.sh 刷新」（词典 3.3） |
| D5 | register-windows.bat 在缺 agent.py 时双击 | `[✗] 找不到 agent.py`，退出码 1（词典 五） |

---

## 四、测试结论汇总

| 测试块 | 状态 | 说明 |
|--------|------|------|
| Mac 静态自检 | ✅ 已执行通过 | `bash -n` + `py_compile` 均 OK；shellcheck 未装跳过 |
| install.sh Win/Git Bash 兼容性分析 | ✅ 已静态核对 | 平台专属动作均被 `case` 门控，唯 `/dev/tty` 需真机确认 |
| 场景 A 前台启动 | ⬜ 待执行 | 需 Windows + Git Bash 真机 |
| 场景 B .bat 一键自启 | ⬜ 待执行 | 需 Windows 真机 |
| 场景 C 手动 schtasks | ⬜ 待执行 | 需 Windows 真机 |
| 场景 D 异常回归 | ⬜ 待执行 | 需 Windows 真机 |

**总评**：静态层面无阻塞性问题，代码不会因语法或平台命令误用而崩。
真机功能验证（A/B/C/D）尚未进行，拿到 Windows 机器后照上表逐项打勾即可。
建议优先验证 **A8（自启分支门控）** 和 **A3/`/dev/tty` 交互读取**，这两处是
Windows 与 mac/linux 差异最大、最可能出问题的点。

> 复测时若某步实际结果与「预期结果」不符，把该行状态改成 ❌ 并贴出真实输出，
> 再对照 `TROUBLESHOOTING.md` 定位。
