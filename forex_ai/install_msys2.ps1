<#
.SYNOPSIS
Downloads and installs MSYS2 and the MinGW-w64 toolchain for Windows.

.DESCRIPTION
This script downloads the official MSYS2 installer, installs it to the default
location (C:\msys64), and then uses pacman to install the x86_64 MinGW toolchain.

.NOTES
Run this script from an elevated PowerShell prompt if you want install paths to work
without additional permission prompts.
#>

param(
    [string]$InstallDir = "$env:SystemDrive\msys64",
    [string]$Msys2Url = "https://github.com/msys2/msys2-installer/releases/download/2026-03-22/msys2-x86_64-20260322.exe"
)

function Test-Administrator {
    $current = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($current)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Administrator)) {
    Write-Warning "Administrator privileges are recommended for MSYS2 installation."
    Write-Warning "If installation fails, rerun this script from an elevated PowerShell prompt."
}

$installerName = Split-Path -Path $Msys2Url -Leaf
$installerPath = Join-Path -Path $env:TEMP -ChildPath $installerName

if (-not (Test-Path -Path $installerPath)) {
    Write-Host "Downloading MSYS2 installer to $installerPath..."
    Invoke-WebRequest -Uri $Msys2Url -OutFile $installerPath
} else {
    Write-Host "MSYS2 installer already downloaded at $installerPath."
}

if (-not (Test-Path -Path $InstallDir)) {
    Write-Host "Installing MSYS2 to $InstallDir..."
    $args = @('/S', "/D=$InstallDir")
    Start-Process -FilePath $installerPath -ArgumentList $args -Wait
} else {
    Write-Host "MSYS2 already installed at $InstallDir."
}

$bashPath = Join-Path -Path $InstallDir -ChildPath 'usr\bin\bash.exe'
if (-not (Test-Path -Path $bashPath)) {
    throw "MSYS2 bash not found at $bashPath. Please verify that MSYS2 installed successfully."
}

Write-Host "Updating MSYS2 package database and core packages..."
& $bashPath -lc "pacman --noconfirm -Syuu"
Write-Host "Installing MinGW-w64 x86_64 toolchain..."
& $bashPath -lc "pacman --noconfirm -S --needed base-devel mingw-w64-x86_64-toolchain"

Write-Host "MSYS2 and MinGW-w64 installation complete."
$mingwPath = Join-Path -Path $InstallDir -ChildPath 'mingw64\bin'
$existingPath = [Environment]::GetEnvironmentVariable('PATH', 'User')
if ([string]::IsNullOrWhiteSpace($existingPath)) {
    [Environment]::SetEnvironmentVariable('PATH', $mingwPath, 'User')
    Write-Host "Added $mingwPath to user PATH."
} elseif (-not ($existingPath.Split(';') -contains $mingwPath)) {
    [Environment]::SetEnvironmentVariable('PATH', "$existingPath;$mingwPath", 'User')
    Write-Host "Added $mingwPath to user PATH."
} else {
    Write-Host "$mingwPath is already in user PATH."
}
Write-Host "Restart VS Code or open a new shell to use gcc from PATH."
