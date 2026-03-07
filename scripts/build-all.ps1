# Build script for complete STTS application
# Run from the project root directory

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  STTS Full Build Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Step 1: Build Python backend
Write-Host "`nStep 1: Building Python backend..." -ForegroundColor Yellow
& .\scripts\build-backend.ps1

# Step 2: Build frontend
Write-Host "`nStep 2: Building frontend..." -ForegroundColor Yellow
npm run build

# Step 3: Build launcher executable
Write-Host "`nStep 3: Building launcher..." -ForegroundColor Yellow
& .\scripts\build-launcher.ps1

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "  Build Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Output files:" -ForegroundColor Cyan
Write-Host "  - STTS.exe (launcher - double-click to start)" -ForegroundColor White
Write-Host "  - python\dist\stts-backend.exe (backend)" -ForegroundColor White
Write-Host "  - dist\ (frontend files)" -ForegroundColor White
