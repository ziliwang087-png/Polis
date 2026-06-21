@echo off
REM =====================================================================
REM  Polis BYOA - Windows 一键注册开机自启（任务计划程序）
REM  =====================================================================
REM  双击本文件即可：自动找 pythonw.exe / agent.py / polis-byoa.env，
REM  填好 polis-byoa-task.xml 的占位符，再用 schtasks 注册任务。
REM
REM  约定：agent.py 与 polis-byoa.env 默认在 %USERPROFILE%\.polis-byoa\
REM  （install.sh 的默认安装目录）。不在的话脚本会提示手动填。
REM
REM  退出码：0=成功  1=缺文件  2=注册失败
REM =====================================================================
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1

set "TASK_NAME=PolisBYOA"
set "BYOA_DIR=%USERPROFILE%\.polis-byoa"
set "AGENT_PY=%BYOA_DIR%\agent.py"
set "ENV_FILE=%BYOA_DIR%\polis-byoa.env"
set "SCRIPT_DIR=%~dp0"
set "XML_TPL=%SCRIPT_DIR%polis-byoa-task.xml"
set "XML_OUT=%TEMP%\polis-byoa-task.filled.xml"

echo.
echo ============================================================
echo   Polis BYOA - Windows 开机自启注册
echo ============================================================
echo.

REM ---- 1) 找 pythonw.exe（优先，不弹黑窗）；退而求其次 python.exe ----
set "PYTHON="
for %%P in (pythonw.exe) do (
  if not defined PYTHON set "PYTHON=%%~$PATH:P"
)
if not defined PYTHON (
  for %%P in (python.exe) do (
    if not defined PYTHON set "PYTHON=%%~$PATH:P"
  )
)
if not defined PYTHON (
  echo [✗] 没在 PATH 里找到 pythonw.exe / python.exe。
  echo     请先装 Python 3.7+（python.org），安装时勾选 "Add to PATH"。
  goto :fail_files
)
echo [▸] Python: %PYTHON%

REM ---- 2) 校验 agent.py / polis-byoa.env 存在 ----
if not exist "%AGENT_PY%" (
  echo [✗] 找不到 agent.py：%AGENT_PY%
  echo     请先跑 install.sh / bootstrap.py 完成安装。
  goto :fail_files
)
if not exist "%ENV_FILE%" (
  echo [✗] 找不到配置文件：%ENV_FILE%
  echo     请先跑 install.sh / bootstrap.py 生成 polis-byoa.env。
  goto :fail_files
)
echo [▸] agent.py : %AGENT_PY%
echo [▸] env 文件 : %ENV_FILE%

REM ---- 3) 校验 XML 模板存在 ----
if not exist "%XML_TPL%" (
  echo [✗] 找不到模板：%XML_TPL%
  goto :fail_files
)

REM ---- 4) 取当前用户（域\用户名）----
set "WHO=%USERDOMAIN%\%USERNAME%"
echo [▸] 用户    : %WHO%
echo.

REM ---- 5) 填占位符，写到 %TEMP% ----
REM   用 PowerShell 做替换，避免 batch 对反斜杠/特殊字符的坑
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$t = Get-Content -Raw -LiteralPath '%XML_TPL%';" ^
  "$t = $t -replace '__PYTHON__',   [Regex]::Escape('%PYTHON%').Replace('\\','\');" ^
  "$t = $t -replace '__AGENT_PY__', [Regex]::Escape('%AGENT_PY%').Replace('\\','\');" ^
  "$t = $t -replace '__ENV_FILE__', [Regex]::Escape('%ENV_FILE%').Replace('\\','\');" ^
  "$t = $t -replace '__USERID__',   '%WHO%';" ^
  "Set-Content -LiteralPath '%XML_OUT%' -Value $t -Encoding Unicode"
if errorlevel 1 (
  echo [✗] 占位符替换失败（PowerShell）。
  goto :fail_register
)
echo [▸] 已生成填好的任务文件：%XML_OUT%

REM ---- 6) 若任务已存在，先删旧的（幂等）----
schtasks /Query /TN "%TASK_NAME%" >nul 2>&1
if not errorlevel 1 (
  echo [!] 已存在同名任务 "%TASK_NAME%"，先删除旧任务……
  schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>&1
)

REM ---- 7) 注册 ----
echo [▸] 注册任务 "%TASK_NAME%" ……
schtasks /Create /TN "%TASK_NAME%" /XML "%XML_OUT%" /F
if errorlevel 1 (
  echo [✗] 注册失败。常见原因：需要管理员权限 / XML 被安全软件拦。
  echo     可右键 "以管理员身份运行" 再试，或看上方报错。
  goto :fail_register
)
echo [✓] 任务已注册。

REM ---- 8) 立即跑一次（不用等下次登录）----
echo [▸] 立即启动一次……
schtasks /Run /TN "%TASK_NAME%" >nul 2>&1
if errorlevel 1 (
  echo [!] 立即启动失败（不影响下次登录自启）。可手动：schtasks /Run /TN "%TASK_NAME%"
) else (
  echo [✓] 已在后台启动。
)

echo.
echo ============================================================
echo   完成。常用命令：
echo     看状态： schtasks /Query /TN "%TASK_NAME%" /V /FO LIST
echo     手动起： schtasks /Run    /TN "%TASK_NAME%"
echo     删除（停自启）： schtasks /Delete /TN "%TASK_NAME%" /F
echo   日志在 agent 端 / 后端 agent 状态查看。
echo ============================================================
echo.
pause
endlocal
exit /b 0

:fail_files
echo.
pause
endlocal
exit /b 1

:fail_register
echo.
pause
endlocal
exit /b 2
