@echo off
REM MaiBot 启动脚本
REM 此脚本将自动激活虚拟环境并启动 MaiBot

echo ========================================
echo         MaiBot 启动脚本
echo ========================================
echo.

REM 获取脚本所在目录
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo 当前目录: %SCRIPT_DIR%
echo.

REM 检查虚拟环境是否存在
if not exist "venv\Scripts\activate.bat" (
    echo 错误: 未找到虚拟环境 (venv\Scripts\activate.bat)
    echo 请先运行以下命令创建虚拟环境:
    echo python -m venv venv
    echo venv\Scripts\activate
    echo pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo 正在激活虚拟环境...
call venv\Scripts\activate.bat

if %errorlevel% neq 0 (
    echo 错误: 虚拟环境激活失败
    pause
    exit /b 1
)

echo 虚拟环境已激活
echo.

REM 检查 bot.py 是否存在
if not exist "bot.py" (
    echo 错误: 未找到 bot.py 文件
    pause
    exit /b 1
)

echo 正在启动 MaiBot...
echo 按 Ctrl+C 停止 MaiBot
echo.

REM 启动 MaiBot
python bot.py

REM 退出时停顿一下，让用户看到输出
echo.
echo MaiBot 已停止运行
pause




