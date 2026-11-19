# Ejecutar desde la raiz del repositorio: .\scripts\setup_windows.ps1
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $projectRoot
if (Get-Command py -ErrorAction SilentlyContinue) {
  & py -3 -m venv .venv
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
  & python -m venv .venv
} else {
  throw 'Instala Python 3.11+ antes de ejecutar este script.'
}
if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno virtual.' }
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
& $pythonExe -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw 'Fallo la instalacion de dependencias.' }
& $pythonExe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'La validacion inicial fallo.' }
Write-Host 'Entorno local listo. Pendiente implementar SAD y las arquitecturas.' -ForegroundColor Green
