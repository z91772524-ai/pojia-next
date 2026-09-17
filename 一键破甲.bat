@echo off
rem ==================================================================
rem  Pojia YiJianTong v6  --  launcher
rem
rem  This file is deliberately 100%% ASCII. A .bat that contains any
rem  non-ASCII byte gets mangled when cmd.exe parses it under the
rem  wrong code page, and the whole script falls apart.  All Chinese
rem  text lives in the .md docs and inside the Python file.
rem  The target .py is located by wildcard because its name is
rem  non-ASCII as well -- never write that name into this file.
rem ==================================================================

cd /d "%~dp0"

set "SCRIPT="
for %%F in ("%~dp0*.py") do if not defined SCRIPT set "SCRIPT=%%~fF"

if not defined SCRIPT (
    echo.
    echo   [!] No .py file found next to this launcher.
    echo       Keep the .bat and the .py in the same folder.
    echo.
    pause
    exit /b 1
)

rem ---- 1) python on PATH ----
where python >nul 2>&1
if %errorlevel%==0 set "PYEXE=python"

rem ---- 2) Windows py launcher ----
if not defined PYEXE (
    where py >nul 2>&1
    if %errorlevel%==0 set "PYEXE=py"
)

rem ---- 3) python bundled with WorkBuddy ----
if not defined PYEXE (
    for /d %%D in ("%USERPROFILE%\.workbuddy\binaries\python\versions\*") do (
        if exist "%%D\python.exe" set "PYEXE=%%D\python.exe"
    )
)

if not defined PYEXE (
    echo.
    echo   [!] Python not found.
    echo.
    echo       Install Python 3.8 or newer from:
    echo         https://www.python.org/downloads/
    echo       Remember to tick  "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)

rem switch the console to UTF-8 so the Python side prints Chinese correctly
chcp 65001 >nul

"%PYEXE%" "%SCRIPT%" %*
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
    echo.
    echo   [exit code %RC%]
    pause
)
