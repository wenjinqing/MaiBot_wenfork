@echo off
chcp 65001 >nul
echo ========================================
echo 启动伊伊 (QQ: 1033245881)
echo ========================================
echo.

REM 配置快速登录环境变量
set ACCOUNT=1033245881
set NAPCAT_QUICK_PASSWORD=021207klsh

REM 使用快速登录，传入 QQ 号
launcher-user.bat 1033245881

pause
