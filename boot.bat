@echo off
title CockyOS
cd /d "%~dp0"
set "COCKY_PY=py"
rem Python koji dolazi s CockyOS-om (runtime\windows-x64), ako postoji i ako je 64-bitni Windows
if exist "runtime\windows-x64\python.exe" (
  if /i not "%PROCESSOR_ARCHITECTURE%"=="x86" set "COCKY_PY=runtime\windows-x64\python.exe"
  if defined PROCESSOR_ARCHITEW6432 set "COCKY_PY=runtime\windows-x64\python.exe"
)
"%COCKY_PY%" CockLoader.py
pause
