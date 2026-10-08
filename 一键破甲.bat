@echo off
rem ==================================================================
rem  Pojia YiJianTong v8.0  --  launcher
rem
rem  This file is deliberately 100% ASCII. A .bat that contains any
rem  non-ASCII byte gets mangled when cmd.exe parses it under the
rem  wrong code page, and the whole script falls apart.  All Chinese
rem  text lives in the .md docs and inside the Python files.
rem  The target .py / GUI .exe are located by wildcard and size
rem  because their names are non-ASCII -- never write those names here.
rem
rem  v8.0 behaviour:
rem    - double-click (no arguments)  ->  GUI exe (*GUI.exe) next to
rem      this launcher; without the exe, the classic CLI menu.
rem    - any argument                 ->  command-line interface
rem      (the GUI exe is a windowless build, so CLI output must go
rem      through Python to be visible in this console).
rem
rem  How the CORE .py is found: the repo also holds small helper .py
rem  files (hash fillers, release scripts) and the ~50 KB GUI .py.
rem  The sealed core is the only .py over 100 KB -- pick that one.
rem ==================================================================

cd /d "%~dp0"

rem ---- locate the CORE .py: the only .py over 100 KB in this folder ----
set "SCRIPT="
for %%F in ("%~dp0*.py") do if %%~zF GTR 100000 set "SCRIPT=%%~fF"

rem ---- locate the GUI exe (non-ASCII name, found by wildcard) ----
set "GUIEXE="
for %%F in ("%~dp0*GUI.exe") do if not defined GUIEXE set "GUIEXE=%%~fF"

rem ---- double-click and the GUI exe is sitting right there -> GUI ----
if "%~1"=="" if defined GUIEXE (
    start "" "%GUIEXE%"
    exit /b 0
)

if not defined SCRIPT (
    echo.
    echo   [!] The core .py was not found next to this launcher.
    echo       Keep the .bat and the core .py in the same folder.
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
    echo       Without Python, double-click still works if the GUI
    echo       exe is present next to this launcher.
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
