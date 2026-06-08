@echo off
setlocal
REM Try to build feature_engine.c into a DLL using gcc (mingw) if available
if exist C:\msys64\mingw64\bin\gcc.exe set "GCC=C:\msys64\mingw64\bin\gcc.exe"
if not defined GCC if exist C:\MinGW\bin\gcc.exe set "GCC=C:\MinGW\bin\gcc.exe"
if not defined GCC if exist C:\MinGW64\bin\gcc.exe set "GCC=C:\MinGW64\bin\gcc.exe"
if not defined GCC set "GCC=gcc"
%GCC% -O3 -shared -o core\engine\feature_engine.dll -fPIC core\engine\feature_engine.c
if %ERRORLEVEL% neq 0 (
    echo Build failed. Ensure you have gcc (mingw) available in PATH or installed via MSYS2.
    exit /b 1
)
echo Built core\engine\feature_engine.dll
endlocal
