# Dot-sourced after common.ps1. Build-PyWheel VERSION OUT_DIR: stage bshell\py with the shared
# frontend and icons, then pip wheel it. Used by bshell-py and by the PyInstaller variant.
function Build-PyWheel {
    param([string]$Ver, [string]$OutDir)
    $stage = Join-Path $Build ('wheel-stage-' + $Ver)
    if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
    New-Item -ItemType Directory -Force -Path $stage | Out-Null
    New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
    $src = Join-Path $Root 'bshell\py'
    Copy-Item (Join-Path $src 'pyproject.toml') $stage
    Copy-Item (Join-Path $src 'README.md') $stage
    Copy-Item -Recurse (Join-Path $src 'src') $stage
    Get-ChildItem -Path $stage -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
    $pkg = Join-Path $stage 'src\benchnotes'
    if (Test-Path (Join-Path $pkg 'frontend')) { Remove-Item -Recurse -Force (Join-Path $pkg 'frontend') }
    Invoke-Checked $Python @((Join-Path $Root 'scripts\stage_frontend.py'), 'bshell-py', (Join-Path $pkg 'frontend'))
    Copy-Item (Join-Path $Root 'assets\icons\icon.icns') $pkg
    Copy-Item (Join-Path $Root 'assets\icons\icon.ico') $pkg
    Set-Content -Path (Join-Path $pkg '_version.py') -Value ('__version__ = ' + [char]34 + $Ver + [char]34) -Encoding Ascii
    Push-Location $stage
    try { Invoke-Checked $Python @('-m', 'pip', 'wheel', '.', '--no-deps', '--quiet', '-w', $OutDir) }
    finally { Pop-Location }
}
