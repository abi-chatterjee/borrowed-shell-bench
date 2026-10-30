# Build the bshell-py artifacts on Windows (pure Python wheel + install scripts).
. (Join-Path $PSScriptRoot '..\..\scripts\common.ps1')
& (Join-Path $Root 'bshell\py\build.ps1')
if ($LASTEXITCODE -ne 0) { throw 'bshell-py build failed' }
