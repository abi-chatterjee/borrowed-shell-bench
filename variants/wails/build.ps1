# Build the Wails v2 variant on Windows with wails build defaults, unsigned.
. (Join-Path $PSScriptRoot '..\..\scripts\common.ps1')
$WailsVersion = 'v2.17.0'
$Stage = Join-Path $Build 'wails'
if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
if (Test-Path (Join-Path $Dist 'wails')) { Remove-Item -Recurse -Force (Join-Path $Dist 'wails') }
New-Item -ItemType Directory -Force -Path (Join-Path $Stage 'build') | Out-Null
$src = Join-Path $Root 'variants\wails'
foreach ($f in 'go.mod', 'wails.json', 'version.go', 'main.go', 'app.go') { Copy-Item (Join-Path $src $f) $Stage }
if (Test-Path (Join-Path $src 'go.sum')) { Copy-Item (Join-Path $src 'go.sum') $Stage }
Copy-Item -Recurse (Join-Path $src 'store') (Join-Path $Stage 'store')
Copy-Item (Join-Path $Root 'assets\icons\icon.png') (Join-Path $Stage 'build\appicon.png')
Invoke-Checked $Python @((Join-Path $Root 'scripts\stage_frontend.py'), 'wails', (Join-Path $Stage 'frontend'))
Invoke-Checked $Python @((Join-Path $Root 'scripts\render.py'), $Stage, $Version)
Push-Location $Stage
try {
    if (-not (Get-Command wails -ErrorAction SilentlyContinue)) {
        Invoke-Checked 'go' @('install', ('github.com/wailsapp/wails/v2/cmd/wails@' + $WailsVersion))
        $env:PATH = (& go env GOPATH).Trim() + '\bin;' + $env:PATH
    }
    Invoke-Checked 'go' @('mod', 'tidy')
    Invoke-Checked 'wails' @('build', '-clean')
}
finally { Pop-Location }
$Pack = Join-Path $Build 'wails-pack'
if (Test-Path $Pack) { Remove-Item -Recurse -Force $Pack }
New-Item -ItemType Directory -Force -Path $Pack | Out-Null
Copy-Item (Join-Path $Stage 'build\bin\Bench Notes (wails).exe') $Pack
$goV = (& go env GOVERSION).Trim()
Complete-Zip 'wails' $Pack 'exe' 'Bench Notes (wails).exe' @(('go=' + $goV), ('wails=' + $WailsVersion))
