@echo off
rem Double-click to install LocalVault on Windows. Pass -Uninstall to remove it.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
echo.
pause
