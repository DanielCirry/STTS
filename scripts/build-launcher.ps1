# Build script for STTS Launcher executable
# Run from the project root directory

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Building STTS Launcher" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$projectRoot = Split-Path -Parent $PSScriptRoot

# Step 1: Create the icon
Write-Host "`nStep 1: Creating icon..." -ForegroundColor Yellow
Push-Location $projectRoot

try {
    # Check if Pillow is installed
    $pillowInstalled = python -c "import PIL" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing Pillow for icon generation..." -ForegroundColor Yellow
        pip install Pillow
    }

    python scripts\create-icon.py

    if (-not (Test-Path "assets\stts-icon.ico")) {
        Write-Host "WARNING: Icon generation failed, using default icon" -ForegroundColor Yellow
    } else {
        Write-Host "Icon created successfully!" -ForegroundColor Green
    }
}
catch {
    Write-Host "WARNING: Could not create icon: $_" -ForegroundColor Yellow
}

# Step 2: Build the launcher
Write-Host "`nStep 2: Building launcher executable..." -ForegroundColor Yellow
Push-Location launcher

try {
    # Install PyInstaller if needed
    $pyinstallerInstalled = python -c "import PyInstaller" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing PyInstaller..." -ForegroundColor Yellow
        pip install pyinstaller
    }

    # Build with PyInstaller
    pyinstaller --clean launcher.spec

    # Copy to project root for easy access
    if (Test-Path "dist\STTS.exe") {
        Copy-Item "dist\STTS.exe" "..\STTS.exe" -Force
        Write-Host "Launcher built successfully!" -ForegroundColor Green
        Write-Host "Output: $projectRoot\STTS.exe" -ForegroundColor Cyan
    } else {
        Write-Host "ERROR: Launcher build failed!" -ForegroundColor Red
        exit 1
    }
}
finally {
    Pop-Location
    Pop-Location
}

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "  Launcher Build Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "You can now double-click STTS.exe to start the application." -ForegroundColor Cyan
