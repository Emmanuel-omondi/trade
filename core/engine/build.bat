@echo off
setlocal EnableDelayedExpansion
title Feature Engine Builder

echo.
echo ============================================================
echo   Skelter Forex AI - Feature Engine Builder
echo ============================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "C_FILE=%SCRIPT_DIR%feature_engine.c"
set "OUT_FILE=%SCRIPT_DIR%feature_engine.dll"
set "COMPILER="
set "COMPILER_NAME="

if not exist "%C_FILE%" (
    echo [ERROR] feature_engine.c not found in:
    echo         %SCRIPT_DIR%
    echo.
    pause
    exit /b 1
)

echo [1/4] Searching for C compiler...
echo.

:: ── Try MinGW gcc (most common on Windows for Python devs) ─────────────────
where gcc >nul 2>&1
if !errorlevel! == 0 (
    for /f "tokens=*" %%i in ('where gcc') do set "COMPILER=%%i"
    set "COMPILER_NAME=MinGW GCC"
    goto :found
)

:: ── Try gcc from common MinGW install paths ─────────────────────────────────
for %%P in (
    "C:\msys64\mingw64\bin\gcc.exe"
    "C:\msys64\mingw32\bin\gcc.exe"
    "C:\msys64\ucrt64\bin\gcc.exe"
    "C:\MinGW\bin\gcc.exe"
    "C:\mingw64\bin\gcc.exe"
    "C:\mingw32\bin\gcc.exe"
    "C:\TDM-GCC-64\bin\gcc.exe"
    "C:\TDM-GCC-32\bin\gcc.exe"
    "C:\Program Files\mingw-w64\x86_64-8.1.0-posix-seh-rt_v6-rev0\mingw64\bin\gcc.exe"
    "C:\Program Files (x86)\mingw-w64\i686-8.1.0-posix-dwarf-rt_v6-rev0\mingw32\bin\gcc.exe"
) do (
    if exist %%P (
        set "COMPILER=%%~P"
        set "COMPILER_NAME=MinGW GCC (%%~P)"
        goto :found
    )
)

:: ── Try clang ───────────────────────────────────────────────────────────────
where clang >nul 2>&1
if !errorlevel! == 0 (
    for /f "tokens=*" %%i in ('where clang') do set "COMPILER=%%i"
    set "COMPILER_NAME=LLVM Clang"
    set "USE_CLANG=1"
    goto :found
)

:: ── Try MSVC cl.exe via vswhere ─────────────────────────────────────────────
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if exist "%VSWHERE%" (
    for /f "usebackq tokens=*" %%i in (
        `"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`
    ) do set "VS_PATH=%%i"
    if defined VS_PATH (
        set "VCVARS=!VS_PATH!\VC\Auxiliary\Build\vcvars64.bat"
        if exist "!VCVARS!" (
            set "COMPILER_NAME=MSVC (Visual Studio)"
            set "USE_MSVC=1"
            goto :found_msvc
        )
    )
)

:: ── Try MSVC from common VS paths ───────────────────────────────────────────
for %%V in (2022 2019 2017) do (
    for %%E in (Enterprise Professional Community BuildTools) do (
        set "VCVARS=C:\Program Files\Microsoft Visual Studio\%%V\%%E\VC\Auxiliary\Build\vcvars64.bat"
        if exist "!VCVARS!" (
            set "COMPILER_NAME=MSVC Visual Studio %%V %%E"
            set "USE_MSVC=1"
            goto :found_msvc
        )
        set "VCVARS=C:\Program Files (x86)\Microsoft Visual Studio\%%V\%%E\VC\Auxiliary\Build\vcvars64.bat"
        if exist "!VCVARS!" (
            set "COMPILER_NAME=MSVC Visual Studio %%V %%E"
            set "USE_MSVC=1"
            goto :found_msvc
        )
    )
)

:: ── Nothing found ────────────────────────────────────────────────────────────
echo [ERROR] No C compiler found on this system.
echo.
echo The system is still fully functional without the C engine.
echo The pure Python fallback in features.py is used automatically.
echo.
echo To get ~50x faster feature computation, install one of:
echo.
echo   Option A - MinGW (recommended, free, 5 min):
echo     1. Go to: https://www.msys2.org/
echo     2. Install MSYS2
echo     3. Open MSYS2 terminal and run:
echo            pacman -S mingw-w64-x86_64-gcc
echo     4. Add C:\msys64\mingw64\bin to your PATH
echo     5. Re-run this build.bat
echo.
echo   Option B - Visual Studio Build Tools (free):
echo     https://visualstudio.microsoft.com/visual-cpp-build-tools/
echo.
pause
exit /b 1

:found_msvc
echo [OK] Found compiler: %COMPILER_NAME%
echo.
echo [2/4] Setting up MSVC environment...
call "%VCVARS%" >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] Failed to initialize MSVC environment
    pause
    exit /b 1
)
echo [OK] MSVC environment ready
echo.
echo [3/4] Compiling feature_engine.c with MSVC...
echo.

if exist "%OUT_FILE%" del /f /q "%OUT_FILE%"

cl.exe /nologo /O2 /GL /fp:fast /LD ^
    /D_WIN32 ^
    "%C_FILE%" ^
    /Fe:"%OUT_FILE%" ^
    /link /LTCG /OPT:REF /OPT:ICF ^
    >"%SCRIPT_DIR%build_log.txt" 2>&1

if !errorlevel! neq 0 (
    echo [ERROR] MSVC compilation failed. See build_log.txt for details.
    echo.
    type "%SCRIPT_DIR%build_log.txt"
    pause
    exit /b 1
)

:: clean up MSVC intermediates
if exist "%SCRIPT_DIR%feature_engine.obj" del /f /q "%SCRIPT_DIR%feature_engine.obj"
if exist "%SCRIPT_DIR%feature_engine.exp" del /f /q "%SCRIPT_DIR%feature_engine.exp"
if exist "%SCRIPT_DIR%feature_engine.lib" del /f /q "%SCRIPT_DIR%feature_engine.lib"

goto :verify

:found
echo [OK] Found compiler: %COMPILER_NAME%
echo      Path: %COMPILER%
echo.

:: ── Get version ─────────────────────────────────────────────────────────────
"%COMPILER%" --version 2>nul | findstr /i "gcc clang version" | head -1
echo.

echo [2/4] Checking C file...
echo      Source : %C_FILE%
echo      Output : %OUT_FILE%
echo.

if exist "%OUT_FILE%" (
    echo [INFO] Existing DLL found, will be replaced.
    del /f /q "%OUT_FILE%"
)

echo [3/4] Compiling...
echo.

if defined USE_CLANG (
    "%COMPILER%" -O3 -march=native -ffast-math ^
        -shared -o "%OUT_FILE%" ^
        "%C_FILE%" ^
        -lm ^
        >"%SCRIPT_DIR%build_log.txt" 2>&1
) else (
    :: MinGW GCC - best flags for a 2GB low-spec Windows machine
    "%COMPILER%" -O3 -march=native -ffast-math -funroll-loops ^
        -shared -o "%OUT_FILE%" ^
        "%C_FILE%" ^
        -lm -static-libgcc ^
        >"%SCRIPT_DIR%build_log.txt" 2>&1
)

if !errorlevel! neq 0 (
    echo [ERROR] Compilation failed. Details:
    echo.
    type "%SCRIPT_DIR%build_log.txt"
    echo.
    echo Common fixes:
    echo   - Make sure feature_engine.c exists and is not open in another program
    echo   - Try running this .bat as Administrator
    pause
    exit /b 1
)

:verify
echo [4/4] Verifying output...
echo.

if not exist "%OUT_FILE%" (
    echo [ERROR] DLL was not created even though compiler reported success.
    echo         Check build_log.txt for warnings.
    pause
    exit /b 1
)

for %%F in ("%OUT_FILE%") do set "DLL_SIZE=%%~zF"
echo [OK] feature_engine.dll created successfully
echo      Size   : %DLL_SIZE% bytes
echo      Path   : %OUT_FILE%
echo.

:: ── Quick sanity test via Python ────────────────────────────────────────────
where python >nul 2>&1
if !errorlevel! == 0 (
    echo [TEST] Running quick Python import test...
    python -c "
import ctypes, os, sys
path = r'%OUT_FILE%'
try:
    lib = ctypes.CDLL(path)
    lib.compute_features.restype = ctypes.c_int
    print('[OK] DLL loads and is callable from Python')
except Exception as e:
    print(f'[WARN] DLL created but Python test failed: {e}')
    sys.exit(1)
" 2>&1
    if !errorlevel! neq 0 (
        echo.
        echo [WARN] DLL exists but may have a dependency issue.
        echo        The Python fallback will be used instead.
        echo        Try installing: Visual C++ Redistributable 2019+
    )
) else (
    echo [SKIP] Python not in PATH, skipping import test
)

echo.
echo ============================================================
echo   Build complete!
echo   The AI will now use the fast C engine automatically.
echo   Restart the application to apply.
echo ============================================================
echo.

if exist "%SCRIPT_DIR%build_log.txt" del /f /q "%SCRIPT_DIR%build_log.txt"

pause
exit /b 0
