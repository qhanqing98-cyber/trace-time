@echo off
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo 没找到 python，请先安装 Python 并把它加入 PATH。
    pause
    exit /b 1
)

python -c "import PyInstaller" >nul 2>nul
if errorlevel 1 (
    echo 没找到 PyInstaller，先装一下：
    echo     pip install pyinstaller
    pause
    exit /b 1
)

python -m PyInstaller --noconfirm --clean --noconsole --name TraceTime main.py
if errorlevel 1 (
    echo 打包失败。
    pause
    exit /b 1
)

echo.
echo 打包完成：%~dp0dist\TraceTime\TraceTime.exe
echo 数据统一存在：%%LOCALAPPDATA%%\TraceTime\trace_time.json
echo 想用便携模式（数据跟着 exe 走）就在 exe 旁边放一个 portable.txt
pause
