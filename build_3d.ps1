$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name SpeedHighway3D --add-data "assets;assets" game3d.py
if ($LASTEXITCODE -ne 0) { throw '3D 打包失败' }
