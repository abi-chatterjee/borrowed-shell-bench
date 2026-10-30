# Build the PyInstaller variant on Windows: freeze the benchnotes wheel with PyInstaller
# defaults (onedir, --windowed), then a uniform zip.
. (Join-Path $PSScriptRoot '..\..\scripts\common.ps1')
. (Join-Path $PSScriptRoot '..\..\scripts\py_wheel.ps1')
$PyInstallerVersion = '6.22.3'
$Stage = Join-Path $Build 'pyinstaller'
if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
if (Test-Path (Join-Path $Dist 'pyinstaller')) { Remove-Item -Recurse -Force (Join-Path $Dist 'pyinstaller') }
New-Item -ItemType Directory -Force -Path $Stage | Out-Null
Build-PyWheel $Version (Join-Path $Stage 'wheel')
Invoke-Checked $Python @('-m', 'venv', (Join-Path $Stage 'venv'))
$Vpy = Join-Path $Stage 'venv\Scripts\python.exe'
$wheelFile = (Get-ChildItem (Join-Path $Stage 'wheel') -Filter 'benchnotes-*.whl' | Select-Object -First 1).FullName
Invoke-Checked $Vpy @('-m', 'pip', 'install', '--quiet', '--disable-pip-version-check', $wheelFile, ('pyinstaller==' + $PyInstallerVersion))
Copy-Item (Join-Path $Root 'variants\pyinstaller\app.py') (Join-Path $Stage 'app.py')
$Name = 'Bench Notes (pyinstaller)'
Push-Location $Stage
try {
    Invoke-Checked $Vpy @('-m', 'PyInstaller', '--noconfirm', '--clean', '--name', $Name, '--collect-data', 'benchnotes',
        '--windowed', '--icon', (Join-Path $Root 'assets\icons\icon.ico'), '--hidden-import', 'webview.platforms.edgechromium', 'app.py')
}
finally { Pop-Location }
$Pack = Join-Path $Build 'pyinstaller-pack'
if (Test-Path $Pack) { Remove-Item -Recurse -Force $Pack }
New-Item -ItemType Directory -Force -Path $Pack | Out-Null
Copy-Item -Recurse -Force (Join-Path $Stage ('dist\' + $Name + '\*')) $Pack
$pyV = (& $Vpy -c 'import sys;print(sys.version.split()[0])').Trim()
Complete-Zip 'pyinstaller' $Pack 'exe' ($Name + '.exe') @(('python=' + $pyV), ('pyinstaller=' + $PyInstallerVersion), 'pywebview=6.2.1')
