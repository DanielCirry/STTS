# Build script for STTS Python backend
# Run from the project root directory

$ErrorActionPreference = "Stop"

Write-Host "Building STTS Python Backend..." -ForegroundColor Cyan

# Navigate to python directory
Push-Location python

try {
    # Check if virtual environment exists
    if (-not (Test-Path "venv")) {
        Write-Host "Creating virtual environment..." -ForegroundColor Yellow
        python -m venv venv
    }

    # Activate virtual environment
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    & .\venv\Scripts\Activate.ps1

    # Install dependencies
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    pip install -r requirements.txt
    pip install pyinstaller

    # Build with PyInstaller
    Write-Host "Building executable with PyInstaller..." -ForegroundColor Yellow
    pyinstaller --clean stts.spec

    # Copy to Tauri binaries directory
    $targetDir = "..\src-tauri\binaries"
    if (-not (Test-Path $targetDir)) {
        New-Item -ItemType Directory -Path $targetDir -Force
    }

    # Copy the executable with the correct name for the platform
    $arch = if ([Environment]::Is64BitOperatingSystem) { "x86_64" } else { "i686" }
    $targetName = "stts-backend-$arch-pc-windows-msvc.exe"

    Copy-Item "dist\stts-backend.exe" "$targetDir\$targetName" -Force
    Write-Host "Copied executable to $targetDir\$targetName" -ForegroundColor Green

    Write-Host "Backend build complete!" -ForegroundColor Green
}
finally {
    Pop-Location
}
