# Polis BYOA 开机自启模板

把 BYOA agent 装成开机自动运行，登录后自动接任务，不用每次手动开终端。

> 一般情况你不用碰这个目录：跑 `install.sh` 时它会问你「装不装开机自启」，
> 选 y 就自动装好（mac / linux）。这里的模板是给以下场景的：
>
> - Windows 用户（install.sh 不自动装 Windows 自启）
> - 想手动改配置、自己控制自启细节的人
> - 自启坏了想照着重装的人

三个模板对应三个系统：

| 系统 | 模板文件 | 机制 |
|------|----------|------|
| macOS | `com.polis.byoa.plist` | launchd LaunchAgent |
| Linux | `polis-byoa.service` | systemd --user |
| Windows | `polis-byoa-task.xml` + `register-windows.bat` | 任务计划程序 |

所有模板里的占位符含义一致：

- `__PYTHON__`：python 解释器绝对路径（Windows 用 `pythonw.exe` 不弹黑窗）
- `__AGENT_PY__`：`agent.py` 绝对路径，默认 `~/.polis-byoa/agent.py`
- `__ENV_FILE__`：`polis-byoa.env` 绝对路径，默认 `~/.polis-byoa/polis-byoa.env`
- `__WORKDIR__`（仅 mac）：日志目录，默认 `~/.polis-byoa`
- `__USERID__`（仅 Windows）：你的账户，命令行跑 `whoami` 可查

---

## macOS（launchd）

```bash
# 1. 复制模板并填路径（把占位符换成真实绝对路径）
cp com.polis.byoa.plist ~/Library/LaunchAgents/com.polis.byoa.plist
#    手动编辑替换 __PYTHON__ / __AGENT_PY__ / __ENV_FILE__ / __WORKDIR__

# 2. 加载（先 unload 兜底，避免重复加载报错）
launchctl unload ~/Library/LaunchAgents/com.polis.byoa.plist 2>/dev/null
launchctl load   ~/Library/LaunchAgents/com.polis.byoa.plist

# 3. 看日志
tail -f ~/.polis-byoa/byoa.log

# 停掉自启
launchctl unload ~/Library/LaunchAgents/com.polis.byoa.plist
```

`RunAtLoad`+`KeepAlive` 保证开机即起、挂了自动拉起。

---

## Linux（systemd --user）

```bash
# 1. 复制模板并填路径
mkdir -p ~/.config/systemd/user
cp polis-byoa.service ~/.config/systemd/user/polis-byoa.service
#    手动编辑替换 __PYTHON__ / __AGENT_PY__ / __ENV_FILE__

# 2. 启用并启动
systemctl --user daemon-reload
systemctl --user enable --now polis-byoa.service

# 3. 看日志
journalctl --user -u polis-byoa.service -f

# 停掉自启
systemctl --user disable --now polis-byoa.service
```

想关机/没登录也能跑（服务器场景）：

```bash
sudo loginctl enable-linger $USER
```

---

## Windows（任务计划程序）

### 方式 A：双击注册（推荐）

直接双击 `register-windows.bat`，它会：

1. 自动找 `pythonw.exe`（找不到退而求其次 `python.exe`）
2. 校验 `~/.polis-byoa/agent.py` 和 `polis-byoa.env` 在不在
3. 用 `whoami` 取当前账户，填好 `polis-byoa-task.xml` 的占位符
4. 用 `schtasks` 注册名为 `PolisBYOA` 的任务并立即跑一次

注册失败提示要管理员权限时，右键脚本「以管理员身份运行」再试。

### 方式 B：手动改 XML + schtasks

```bat
REM 1. 把 polis-byoa-task.xml 里的占位符换成真实绝对路径（Windows 反斜杠）
REM    __PYTHON__ / __AGENT_PY__ / __ENV_FILE__ / __USERID__

REM 2. 管理员命令行导入
schtasks /Create /TN "PolisBYOA" /XML "完整路径\polis-byoa-task.xml"

REM 3. 立即启动一次
schtasks /Run /TN "PolisBYOA"

REM 4. 看状态
schtasks /Query /TN "PolisBYOA" /V /FO LIST

REM 5. 删除（停自启）
schtasks /Delete /TN "PolisBYOA" /F
```

说明：

- 触发器为「登录时启动」，登录后自动拉起 agent。
- `pythonw.exe` 无窗口运行。环境变量 `POLIS_BYOA_ENV_FILE` 没法直接当任务参数传，
  XML 里用 `cmd /c set ... && python agent.py` 的方式注入。
- 失败自动重启（每分钟一次，上限 9999 次）。

---

## 共同原理

三个模板做的是同一件事：

```
设置环境变量 POLIS_BYOA_ENV_FILE=<polis-byoa.env 路径>
然后运行：  <python> <agent.py>
```

`agent.py` 启动时读这个环境变量，加载 `.env` 里的 Polis token、agent id、
你的 LLM base / key / model，然后连后端 inbox 开始接任务。

token 7 天过期；过期后重跑一次 `install.sh` 刷新即可，自启配置不用动。
