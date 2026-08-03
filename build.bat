@echo off
REM ---------------------------------------------------------------------
REM  Quick Image Stitcher - Windows build
REM  Double-click this, or run it from a terminal. Produces dist\Stitcher\
REM ---------------------------------------------------------------------
setlocal

set APPNAME=Stitcher
set ENTRY=stitcher.py

REM --- ONEFILE=1 makes a single .exe (slower start, more AV false positives)
REM     ONEFILE=0 makes a folder (fast start, friendlier to antivirus)
set ONEFILE=0

echo.
echo === Checking Python ===
python --version 2>NUL
if errorlevel 1 (
    echo ERROR: python is not on PATH. Install Python 3.10+ from python.org
    echo        and tick "Add python.exe to PATH" during setup.
    pause & exit /b 1
)

echo.
echo === Installing build dependencies ===
python -m pip install --upgrade pip
python -m pip install --upgrade pyinstaller pillow tkinterdnd2
if errorlevel 1 ( echo ERROR: dependency install failed. & pause & exit /b 1 )

echo.
echo === Collecting third-party license texts ===
python collect_licenses.py
if errorlevel 1 (
    echo.
    echo WARNING: some license texts were not found - see the message above.
    echo Fix THIRD-PARTY-LICENSES.txt before distributing this build.
    echo.
    pause
)

echo.
echo === Cleaning previous build ===
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist %APPNAME%.spec del /q %APPNAME%.spec

echo.
echo === Building ===
if "%ONEFILE%"=="1" ( set MODE=--onefile ) else ( set MODE=--onedir )

pyinstaller %MODE% --noconsole --name "%APPNAME%" ^
    --collect-all tkinterdnd2 ^
    --add-data "LICENSE.txt;." ^
    --add-data "THIRD-PARTY-LICENSES.txt;." ^
    %ENTRY%
if errorlevel 1 ( echo ERROR: build failed. & pause & exit /b 1 )

REM --- license files must also sit BESIDE the exe, not just inside it ---
if "%ONEFILE%"=="1" (
    copy /y LICENSE.txt dist\ >NUL
    copy /y THIRD-PARTY-LICENSES.txt dist\ >NUL
) else (
    copy /y LICENSE.txt "dist\%APPNAME%\" >NUL
    copy /y THIRD-PARTY-LICENSES.txt "dist\%APPNAME%\" >NUL
)

echo.
echo === Done ===
echo Output is in the dist folder. Zip that folder to share it.
echo.
echo If the app closes instantly with no window, rebuild without --noconsole
echo to see the traceback: pyinstaller --onedir --name %APPNAME% --collect-all tkinterdnd2 %ENTRY%
echo.
pause
