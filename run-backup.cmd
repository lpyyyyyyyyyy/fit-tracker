@echo off
REM 每天 02:00 定时任务的启动包装。
REM 用 .cmd 而不是直接把 python 路径写进计划任务：
REM   1. 路径改了只动这一个文件
REM   2. 能把输出重定向进日志，方便排查
REM   3. 不依赖"起始位置"设置
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
"C:\Users\32890\AppData\Local\Programs\Python\Python313\python.exe" "%~dp0_backup.py" >> "%~dp0backup.log" 2>&1
exit /b %ERRORLEVEL%
