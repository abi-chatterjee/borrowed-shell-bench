# Build the bshell-node artifacts on Windows (npm tarball + install scripts).
. (Join-Path $PSScriptRoot '..\..\scripts\common.ps1')
& (Join-Path $Root 'bshell\node\build.ps1')
if ($LASTEXITCODE -ne 0) { throw 'bshell-node build failed' }
