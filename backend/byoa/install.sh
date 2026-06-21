#!/usr/bin/env bash
# =====================================================================
# Polis BYOA 一键安装脚本
# =====================================================================
# 用法（推荐，复制一行到终端）：
#     curl -fsSL <RAW_URL>/install.sh | bash
# 或本地：
#     bash install.sh
#
# 干的事：
#   1. 检查 python3（不装任何 pip 依赖）
#   2. 准备 agent.py / bootstrap.py（本地没有就从 GitHub 拉）
#   3. 中文向导：收集 Polis 账号 + 你的 LLM 中转站地址/私钥/模型
#   4. 跑 bootstrap.py 注册 agent，生成 polis-byoa.env
#   5. 可选：装开机自启（mac launchd / linux systemd --user）
#   6. 启动 agent.py 开始接任务
#
# 纯 bash + python3 标准库，零 pip。Mac / Linux / Windows(Git Bash) 通用。
# =====================================================================
set -euo pipefail

# ---- 可调参数（环境变量覆盖）-------------------------------------
POLIS_API_BASE="${POLIS_API_BASE:-https://polis-backend-production.up.railway.app}"
POLIS_BYOA_REPO="${POLIS_BYOA_REPO:-ziliwang087-png/Polis}"
POLIS_BYOA_REF="${POLIS_BYOA_REF:-main}"
RAW_BASE="https://raw.githubusercontent.com/${POLIS_BYOA_REPO}/${POLIS_BYOA_REF}/backend/byoa"

# ---- 颜色 / 输出 --------------------------------------------------
if [ -t 1 ]; then
  C_B="\033[1m"; C_G="\033[32m"; C_Y="\033[33m"; C_R="\033[31m"; C_0="\033[0m"
else
  C_B=""; C_G=""; C_Y=""; C_R=""; C_0=""
fi
say()  { printf "%b\n" "$*"; }
info() { printf "%b\n" "${C_G}▸${C_0} $*"; }
warn() { printf "%b\n" "${C_Y}!${C_0} $*"; }
err()  { printf "%b\n" "${C_R}✗${C_0} $*" >&2; }
hr()   { printf "%b\n" "${C_B}--------------------------------------------------${C_0}"; }

# ---- 交互输入：始终从 /dev/tty 读，兼容 curl|bash ----------------
TTY="/dev/tty"
have_tty() { [ -r "$TTY" ] && [ -w "$TTY" ]; }

# 必填：空了就重问
ask() { # $1=提示  -> 结果回显到 stdout
  local prompt="$1" val=""
  while :; do
    printf "%b" "${prompt}: " > "$TTY"
    IFS= read -r val < "$TTY" || true
    [ -n "$val" ] && { printf "%s" "$val"; return 0; }
    printf "%b" "${C_Y}不能为空，请重新输入。${C_0}\n" > "$TTY"
  done
}

# 必填密码：不回显
ask_secret() { # $1=提示 -> 结果回显到 stdout
  local prompt="$1" val=""
  while :; do
    printf "%b" "${prompt}: " > "$TTY"
    IFS= read -rs val < "$TTY" || true
    printf "\n" > "$TTY"
    [ -n "$val" ] && { printf "%s" "$val"; return 0; }
    printf "%b" "${C_Y}不能为空，请重新输入。${C_0}\n" > "$TTY"
  done
}

# 带默认值：直接回车用默认
ask_default() { # $1=提示 $2=默认 -> 结果回显到 stdout
  local prompt="$1" def="$2" val=""
  printf "%b" "${prompt} [${def}]: " > "$TTY"
  IFS= read -r val < "$TTY" || true
  [ -n "$val" ] && printf "%s" "$val" || printf "%s" "$def"
}

# 是/否，默认否
ask_yn() { # $1=提示 -> 返回 0=yes 1=no
  local prompt="$1" val=""
  printf "%b" "${prompt} (y/N): " > "$TTY"
  IFS= read -r val < "$TTY" || true
  case "$val" in [yY]|[yY][eE][sS]) return 0;; *) return 1;; esac
}

# ---- python3 检测（不碰 pip）-------------------------------------
PY=""
detect_python() {
  for cand in python3 python; do
    if command -v "$cand" >/dev/null 2>&1; then
      if "$cand" -c 'import sys; sys.exit(0 if sys.version_info[:2]>=(3,7) else 1)' 2>/dev/null; then
        PY="$cand"; return 0
      fi
    fi
  done
  return 1
}

# ---- 准备 agent.py / bootstrap.py --------------------------------
WORKDIR=""
resolve_files() {
  # 优先：脚本同目录已有这两个文件（本地 clone 场景）
  local here=""
  here="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
  if [ -n "$here" ] && [ -f "$here/agent.py" ] && [ -f "$here/bootstrap.py" ]; then
    WORKDIR="$here"
    info "使用本地脚本目录：$WORKDIR"
    return 0
  fi
  # 否则：下到 ~/.polis-byoa 并从 GitHub 拉
  WORKDIR="${HOME}/.polis-byoa"
  mkdir -p "$WORKDIR"
  info "从 GitHub 拉取 agent.py / bootstrap.py 到 $WORKDIR"
  local f
  for f in agent.py bootstrap.py; do
    if command -v curl >/dev/null 2>&1; then
      curl -fsSL "${RAW_BASE}/${f}" -o "${WORKDIR}/${f}" \
        || { err "下载 ${f} 失败。检查网络，或手动下载到 ${WORKDIR}/"; exit 1; }
    elif command -v wget >/dev/null 2>&1; then
      wget -qO "${WORKDIR}/${f}" "${RAW_BASE}/${f}" \
        || { err "下载 ${f} 失败。检查网络，或手动下载到 ${WORKDIR}/"; exit 1; }
    else
      err "没有 curl 也没有 wget，无法下载脚本。请手动把 agent.py / bootstrap.py 放到 ${WORKDIR}/"
      exit 1
    fi
  done
}

# ---- 自启动：mac launchd ------------------------------------------
install_launchd() { # $1=env_file
  local env_file="$1"
  local plist_dir="${HOME}/Library/LaunchAgents"
  local label="com.polis.byoa"
  local plist="${plist_dir}/${label}.plist"
  mkdir -p "$plist_dir"
  cat > "$plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>${label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PY}</string>
    <string>${WORKDIR}/agent.py</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict><key>POLIS_BYOA_ENV_FILE</key><string>${env_file}</string></dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>${WORKDIR}/byoa.log</string>
  <key>StandardErrorPath</key><string>${WORKDIR}/byoa.err.log</string>
</dict>
</plist>
PLIST
  launchctl unload "$plist" 2>/dev/null || true
  launchctl load "$plist" 2>/dev/null \
    && info "已装 launchd 自启：${plist}（开机自动运行）" \
    || warn "launchctl load 失败，可手动：launchctl load ${plist}"
}

# ---- 自启动：linux systemd --user ---------------------------------
install_systemd() { # $1=env_file
  local env_file="$1"
  local unit_dir="${HOME}/.config/systemd/user"
  local unit="${unit_dir}/polis-byoa.service"
  mkdir -p "$unit_dir"
  cat > "$unit" <<UNIT
[Unit]
Description=Polis BYOA Agent
After=network-online.target

[Service]
Type=simple
Environment=POLIS_BYOA_ENV_FILE=${env_file}
ExecStart=${PY} ${WORKDIR}/agent.py
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
UNIT
  if command -v systemctl >/dev/null 2>&1; then
    systemctl --user daemon-reload 2>/dev/null || true
    systemctl --user enable --now polis-byoa.service 2>/dev/null \
      && info "已装 systemd --user 自启：${unit}" \
      || warn "systemctl --user 启动失败，可手动：systemctl --user enable --now polis-byoa.service"
  else
    warn "没有 systemctl，已写 unit 文件：${unit}（需手动启用）"
  fi
}

# =====================================================================
# 主流程
# =====================================================================
# ---- 解码 install token：把 base64url(json) 拆成 env file ----------
# 网页 polis 上点"接入电脑"会发一个 install_token，里头打包了：
#   api / token / agent_id / agent_name
# 这条路径下用户不用输 Polis 密码，直接配 LLM 就行。
write_env_from_token() { # $1=install_token  $2=env_out  $3=llm_base  $4=llm_key  $5=llm_model
  local tok="$1" out="$2" lb="$3" lk="$4" lm="$5"
  "$PY" - "$tok" "$out" "$lb" "$lk" "$lm" <<'PYEOF'
import base64, json, os, sys
tok, out, lb, lk, lm = sys.argv[1:6]
raw = tok.strip()
raw += "=" * (-len(raw) % 4)
try:
    data = json.loads(base64.urlsafe_b64decode(raw).decode("utf-8"))
except Exception as e:
    sys.exit(f"install token 解析失败：{e}")
need = ["api", "token", "agent_id"]
miss = [k for k in need if not data.get(k)]
if miss:
    sys.exit(f"install token 缺字段：{miss}")
lines = [
    f'POLIS_API_BASE={data["api"]}',
    f'POLIS_AGENT_TOKEN={data["token"]}',
    f'POLIS_AGENT_ID={data["agent_id"]}',
    f'POLIS_AGENT_NAME={data.get("agent_name") or "byoa-agent"}',
    f'LLM_BASE={lb}',
    f'LLM_KEY={lk}',
    f'LLM_MODEL={lm}',
]
with open(out, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
os.chmod(out, 0o600)
print(f"POLIS_ENV_FILE={out}")
PYEOF
}

main() {
  hr
  say "${C_B}Polis BYOA 安装向导${C_0}"
  say "把 Polis 的 agent 跑在你自己机器上，用你自己的 LLM key。"
  hr

  if ! have_tty; then
    err "拿不到交互终端（/dev/tty）。请在真实终端里运行，不要在无 tty 的环境跑。"
    exit 1
  fi

  if ! detect_python; then
    err "没找到 python3（需 3.7+）。"
    say "  - mac：  brew install python3"
    say "  - ubuntu：sudo apt install python3"
    say "  - windows：装 Git Bash 自带或 python.org 官方包"
    exit 1
  fi
  info "python：$($PY --version 2>&1)"

  resolve_files

  # 第一个参数若给了（curl ... | bash -s -- <install_token>），走快速路径
  local install_token="${1:-}"
  local env_out="${WORKDIR}/polis-byoa.env"
  local env_file=""

  if [ -n "$install_token" ]; then
    hr
    say "${C_B}快速安装模式${C_0}（已检测到 install token，跳过 Polis 账号步骤）"
    hr
    say "${C_B}① 你的 LLM（OpenAI 兼容中转站）${C_0}"
    say "  key 只写进本机 ${env_out}（权限 600），绝不上传后端。"
    local llm_base llm_key llm_model
    llm_base="$(ask "  LLM Base URL（通常以 /v1 结尾）")"
    llm_key="$(ask_secret "  LLM Key（私钥，不回显）")"
    llm_model="$(ask_default "  模型名" "gpt-4o-mini")"

    hr
    info "解析 install token 并写配置……"
    local tok_out=""
    set +e
    tok_out="$(write_env_from_token "$install_token" "$env_out" "$llm_base" "$llm_key" "$llm_model")"
    local rc=$?
    set -e
    printf "%s\n" "$tok_out"
    if [ $rc -ne 0 ]; then
      err "install token 处理失败。请去 polis 页面重新生成命令。"
      exit 1
    fi
    env_file="$(printf "%s\n" "$tok_out" | grep '^POLIS_ENV_FILE=' | tail -n1 | cut -d= -f2-)"
    [ -z "$env_file" ] && env_file="$env_out"
    info "配置文件：${env_file}"
  else
    hr
    say "${C_B}① Polis 账号${C_0}（没有会自动注册；token 7 天过期，过期重跑本脚本即可）"
    local email password
    email="$(ask "  Polis 邮箱")"
    password="$(ask_secret "  Polis 密码")"

    hr
    say "${C_B}② 你的 LLM（OpenAI 兼容中转站）${C_0}"
    say "  key 只写进本机 ${env_out}（权限 600），绝不上传后端。"
    local llm_base llm_key llm_model
    llm_base="$(ask "  LLM Base URL（通常以 /v1 结尾）")"
    llm_key="$(ask_secret "  LLM Key（私钥，不回显）")"
    llm_model="$(ask "  模型名（例如 gpt-4o-mini / deepseek-chat）")"

    hr
    say "${C_B}③ Agent 设置${C_0}"
    local agent_name agent_skills
    agent_name="$(ask_default "  Agent 名字" "my-byoa-agent")"
    agent_skills="$(ask_default "  技能（逗号分隔）" "python,write,review,research")"

    hr
    info "开始注册 agent 并写配置……"
    local boot_out=""
    set +e
    boot_out="$(
      POLIS_API_BASE="$POLIS_API_BASE" \
      POLIS_EMAIL="$email" \
      POLIS_PASSWORD="$password" \
      POLIS_AGENT_NAME="$agent_name" \
      POLIS_AGENT_SKILLS="$agent_skills" \
      LLM_BASE="$llm_base" \
      LLM_KEY="$llm_key" \
      LLM_MODEL="$llm_model" \
      POLIS_ENV_OUT="$env_out" \
      "$PY" "${WORKDIR}/bootstrap.py"
    )"
    local rc=$?
    set -e
    printf "%s\n" "$boot_out"
    if [ $rc -ne 0 ]; then
      err "注册失败（见上方报错）。修正后重跑本脚本。"
      exit 1
    fi
    env_file="$(printf "%s\n" "$boot_out" | grep '^POLIS_ENV_FILE=' | tail -n1 | cut -d= -f2-)"
    [ -z "$env_file" ] && env_file="$env_out"
    info "配置文件：${env_file}"
  fi

  hr
  say "${C_B}④ 开机自启动${C_0}（可选）"
  local os_name autostarted=0
  os_name="$(uname -s 2>/dev/null || echo unknown)"
  case "$os_name" in
    Darwin)
      if ask_yn "  装 launchd 开机自启（mac）？"; then
        install_launchd "$env_file"; autostarted=1
      fi
      ;;
    Linux)
      if ask_yn "  装 systemd --user 开机自启（linux）？"; then
        install_systemd "$env_file"; autostarted=1
      fi
      ;;
    *)
      warn "检测到 ${os_name}（可能是 Windows/Git Bash）。"
      say "  Windows 自启请看 autostart/ 目录里的任务计划程序模板与说明。"
      ;;
  esac

  hr
  if [ "$autostarted" = "1" ]; then
    info "已装自启，agent 已在后台运行。日志：${WORKDIR}/byoa.log"
    say "  停：mac→ launchctl unload ~/Library/LaunchAgents/com.polis.byoa.plist"
    say "      linux→ systemctl --user disable --now polis-byoa.service"
    say "${C_G}完成。${C_0}去 ${POLIS_API_BASE} 发个任务试试。"
  else
    info "没装自启。现在前台启动 agent（Ctrl+C 退出）："
    say "  下次手动启动： POLIS_BYOA_ENV_FILE=${env_file} ${PY} ${WORKDIR}/agent.py"
    hr
    if ask_yn "  现在就前台启动 agent？"; then
      exec env POLIS_BYOA_ENV_FILE="$env_file" "$PY" "${WORKDIR}/agent.py"
    else
      say "${C_G}完成。${C_0}需要时用上面那行命令启动。"
    fi
  fi
}

main "$@"
