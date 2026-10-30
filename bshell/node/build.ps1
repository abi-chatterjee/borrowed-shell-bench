# Build the bshell-node artifacts on Windows: npm tarball(s), install.ps1, manifest.
#   BENCH_VERSION (default 1.0.0), BENCH_UPDATE_VERSION (default 1.0.1)
. (Join-Path $PSScriptRoot '..\..\scripts\common.ps1')
$UpdateVersion = if ($env:BENCH_UPDATE_VERSION) { $env:BENCH_UPDATE_VERSION } else { '1.0.1' }
$Out = Join-Path $Dist 'bshell-node'
if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

function Build-Tarball {
    param([string]$Ver)
    $root2 = Join-Path $Build ('bshell-node-' + $Ver)
    if (Test-Path $root2) { Remove-Item -Recurse -Force $root2 }
    $stage = Join-Path $root2 'package'
    New-Item -ItemType Directory -Force -Path $stage | Out-Null
    $src = Join-Path $Root 'bshell\node'
    foreach ($f in 'package.json', 'README.md') { Copy-Item (Join-Path $src $f) $stage }
    foreach ($d in 'bin', 'src') { Copy-Item -Recurse (Join-Path $src $d) $stage }
    Invoke-Checked $Python @((Join-Path $Root 'scripts\stage_frontend.py'), 'bshell-node', (Join-Path $stage 'frontend'))
    Copy-Item (Join-Path $Root 'assets\icons\icon.icns') $stage
    Copy-Item (Join-Path $Root 'assets\icons\icon.ico') $stage
    $js = 'module.exports = { version: ''' + $Ver + ''' };'
    Set-Content -Path (Join-Path $stage 'src\version.js') -Value $js -Encoding Ascii
    Push-Location $stage
    try {
        Invoke-Checked 'npm' @('version', $Ver, '--no-git-tag-version', '--allow-same-version')
        Invoke-Checked 'npm' @('pack', '--pack-destination', $Out, '--silent')
    }
    finally { Pop-Location }
}

Build-Tarball $Version
Build-Tarball $UpdateVersion
Copy-Item (Join-Path $Root 'bshell\node\install.sh') $Out
Copy-Item (Join-Path $Root 'bshell\node\install.ps1') $Out
$tgz = 'benchnotes-' + $Version + '.tgz'
Invoke-Checked $Python @((Join-Path $Root 'scripts\check_frontend.py'), '--archive', (Join-Path $Out $tgz), 'http')
$nodeV = (& node --version).Trim()
$npmV = (& npm --version).Trim()
Invoke-Checked $Python @((Join-Path $Root 'scripts\write_manifest.py'), '--dir', $Out, '--variant', 'bshell-node', '--version', $Version,
    '--kind', 'installer', '--installer', 'install.ps1', '--artifact', 'install.ps1', '--artifact', $tgz,
    '--update-artifact', ('benchnotes-' + $UpdateVersion + '.tgz'),
    '--tool', ('node=' + $nodeV), '--tool', ('npm=' + $npmV), '--tool', 'webview-binding=@webviewjs/webview@0.4.9')
Write-Host ('bshell-node built in ' + $Out)
