$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name SpeedHighway game.py
if ($LASTEXITCODE -ne 0) { throw '打包失败' }
