param([string]$PythonExecutable)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

if (-not $PythonExecutable) {
    $runtimeRoot = Join-Path $PSScriptRoot '.runtime'
    if (Test-Path -LiteralPath $runtimeRoot) {
        $candidate = Get-ChildItem -LiteralPath $runtimeRoot -Directory |
            Where-Object { $_.Name -like 'cpython-3.11.*-windows-x86_64-none' } |
            Sort-Object Name -Descending | Select-Object -First 1
        if ($candidate) { $PythonExecutable = Join-Path $candidate.FullName 'python.exe' }
    }
}
if (-not $PythonExecutable -and (Get-Command py.exe -ErrorAction SilentlyContinue)) {
    $candidate = & py.exe -3.11 -c 'import sys; print(sys.executable)' 2>$null
    if ($LASTEXITCODE -eq 0) { $PythonExecutable = [string]($candidate | Select-Object -Last 1) }
}
if (-not $PythonExecutable) { throw 'Install Python 3.11 or provide -PythonExecutable with its absolute path.' }
$version = & $PythonExecutable -c 'import sys; print("%d.%d" % sys.version_info[:2])'
if ($LASTEXITCODE -ne 0 -or $version -ne '3.11') { throw 'This build requires Python 3.11.' }
& $PythonExecutable -m venv '.venv-dev'
if ($LASTEXITCODE -ne 0) { throw 'Could not create .venv-dev; the old .venv was not changed.' }
$developmentPython = Join-Path $PSScriptRoot '.venv-dev\Scripts\python.exe'
& $developmentPython -m pip install -r 'requirements-windows-lock.txt' --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $developmentPython -c 'import pygame, panda3d.core; print("Game dependencies are ready.")'
if ($LASTEXITCODE -ne 0) { throw 'Dependency verification failed.' }
