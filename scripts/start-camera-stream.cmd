@echo off
title Smart Waste Camera Stream
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-camera-stream.ps1" %*
if errorlevel 1 pause
