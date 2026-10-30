# Build every variant (or the ones named in $env:BENCH_VARIANTS, space separated) for this
# machine, then run each variant's smoke check. Every variant is attempted even if an
# earlier one fails; the exit code is non-zero if any build or smoke check failed.
#   powershell -ExecutionPolicy Bypass -File scripts\build_all.ps1
. (Join-Path $PSScriptRoot 'common.ps1')
$ErrorActionPreference = 'Continue'
$list = if ($env:BENCH_VARIANTS) { $env:BENCH_VARIANTS -split '\s+' } else { @('electron', 'tauri', 'wails', 'neutralino', 'pyinstaller', 'bshell-py', 'bshell-node') }
$failed = @()
$summary = @()
foreach ($v in $list) {
    Write-Host ('=== build ' + $v + ' (' + $Platform + ') ===')
    $b = 'built'
    try {
        & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root ('variants\' + $v + '\build.ps1'))
        if ($LASTEXITCODE -ne 0) { throw ('exit code ' + $LASTEXITCODE) }
    }
    catch {
        $b = 'BUILD-FAILED'
        $failed += $v
        Write-Host $_
    }
    $s = 'skipped'
    if ($b -eq 'built' -and -not $env:BENCH_SKIP_SMOKE) {
        Write-Host ('=== smoke ' + $v + ' ===')
        & $Python (Join-Path $Root ('variants\' + $v + '\smoke.py'))
        if ($LASTEXITCODE -eq 0) { $s = 'ok' } else { $s = 'SMOKE-FAILED'; $failed += $v }
    }
    $summary += ($v + ': ' + $b + ', smoke ' + $s)
}
Write-Host ('=== summary for ' + $Platform + ' ===')
$summary | ForEach-Object { Write-Host $_ }
if ($failed.Count -gt 0) { Write-Host ('failed: ' + ($failed -join ' ')); exit 1 }
