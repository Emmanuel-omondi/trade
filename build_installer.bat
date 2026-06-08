@echo off
setlocal
if not defined PYINSTALLER (
    set PYINSTALLER=pyinstaller
)
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
set ICON=assets\app.ico
if not exist %ICON% set ICON=
%PYINSTALLER% --noconfirm --clean --add-data "ui/style.qss;ui" --add-data "config/settings.json;config" --add-data "db/forex_ai.db;db" --name SkelterTraderAgent --onefile --windowed main.py %ICON%
if %ERRORLEVEL% neq 0 (
    echo PyInstaller failed. Ensure pyinstaller is installed in the active environment.
    exit /b 1
)
echo Built installer in dist\SkelterTraderAgent.exe
endlocal
