$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$developmentPython = Join-Path $PSScriptRoot '.venv-dev\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $developmentPython)) { throw 'Run setup_dev.ps1 first.' }
$checkDirectory = Join-Path $PSScriptRoot 'reports\build-check'
New-Item -ItemType Directory -Path $checkDirectory -Force | Out-Null
$previousPythonPath = $env:PYTHONPATH
$previousVideoDriver = $env:SDL_VIDEODRIVER
$previousAudioDriver = $env:SDL_AUDIODRIVER
try {
    $env:PYTHONPATH = $PSScriptRoot
    $env:SDL_VIDEODRIVER = 'dummy'
    $env:SDL_AUDIODRIVER = 'dummy'
    Push-Location $checkDirectory
    try { & $developmentPython -B -m unittest discover -s (Join-Path $PSScriptRoot 'tests') -v }
    finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed; no preview package was built.' }
} finally {
    $env:PYTHONPATH = $previousPythonPath
    $env:SDL_VIDEODRIVER = $previousVideoDriver
    $env:SDL_AUDIODRIVER = $previousAudioDriver
}
& $developmentPython -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name 'SpeedHighway-Escort-Preview' --distpath 'dist\escort-preview' `
    --workpath 'build\escort-preview' --specpath 'build\escort-preview' `
    --add-data "$PSScriptRoot\assets;assets" --collect-all panda3d 'escort_launcher.py'
if ($LASTEXITCODE -ne 0) { throw 'Preview packaging failed.' }
Write-Output 'Built dist\escort-preview\SpeedHighway-Escort-Preview.exe (local preview; not published).'
