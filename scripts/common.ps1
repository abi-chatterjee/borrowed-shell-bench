# Dot-sourced by every build.ps1 (Windows PowerShell 5.1 or PowerShell 7).
# Provides: $Root, $Version, $Platform, $Dist, $Build, $Python
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = if ($env:PYTHON) { $env:PYTHON } else { 'python' }
$Version = if ($env:BENCH_VERSION) { $env:BENCH_VERSION } else { '1.0.0' }
$Platform = (& $Python (Join-Path $Root 'scripts\platform_tag.py')).Trim()
$Dist = if ($env:BENCH_DIST) { $env:BENCH_DIST } else { Join-Path $Root ('dist\' + $Platform) }
$Build = if ($env:BENCH_BUILD) { $env:BENCH_BUILD } else { Join-Path $Root ('build\' + $Platform) }

function Invoke-Checked {
    # Run a native command and stop on a non-zero exit code.
    param([string]$Exe, [string[]]$Arguments)
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw ('command failed (' + $LASTEXITCODE + '): ' + $Exe + ' ' + ($Arguments -join ' ')) }
}

function Complete-Zip {
    # Zip SrcDir into $Dist\Variant and write manifest.json.
    param([string]$Variant, [string]$SrcDir, [string]$LaunchKind, [string]$LaunchPath, [string[]]$Tools)
    $outDir = Join-Path $Dist $Variant
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
    $zip = $Variant + '-' + $Version + '-' + $Platform + '.zip'
    Invoke-Checked $Python @((Join-Path $Root 'scripts\package_zip.py'), $SrcDir, (Join-Path $outDir $zip))
    $args = @((Join-Path $Root 'scripts\write_manifest.py'), '--dir', $outDir, '--variant', $Variant, '--version', $Version,
        '--kind', 'zip', '--artifact', $zip, '--launch-kind', $LaunchKind, '--launch-path', $LaunchPath)
    foreach ($t in $Tools) { $args += @('--tool', $t) }
    Invoke-Checked $Python $args
    Write-Host ($Variant + ' built: ' + (Join-Path $outDir $zip))
}
