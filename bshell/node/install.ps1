# Bench Notes (bshell-node) installer for Windows. PowerShell 5.1 or later.
#
#   irm <url>/install.ps1 | iex
#
# Per user, no administrator rights:
#   1. find Node.js 24+ (or download a private official build, checksum-verified)
#   2. npm install the benchnotes tarball (and the native web view library)
#   3. create a Start menu shortcut that runs node.exe minimised; the app then
#      re-launches itself hidden and detached (node.exe is a console program)
#   4. run the self-test (benchnotes ui --check)
#
# Node 24+ is required because the platform packages of @webviewjs/webview
# declare engines.node >= 24 (npm silently skips them on older Node).
#
# Environment overrides (all optional):
#   BENCHNOTES_HOME                   install root         (default %LOCALAPPDATA%\BenchNotes\bshell-node-home)
#   BENCHNOTES_APPS_DIR               shortcut folder      (default: your Start menu Programs folder)
#   BENCHNOTES_TARBALL                local tarball path or URL (default: benchnotes from the npm registry)
#   BENCHNOTES_NODE_VERSION           Node downloaded when none is usable (default 24.22.1)
#   BENCHNOTES_NODE_DIST_URL          Node download base   (default https://nodejs.org/dist)
#   BENCHNOTES_FORCE_RUNTIME_INSTALL  1 = ignore any Node found, download one
#   BENCHNOTES_SKIP_BACKEND_CHECK     1 = self-test without the window backend (CI only)
#
# House rules for this file, checked by bench/tests/test_install_ps1.py:
#   * ASCII only (Windows PowerShell 5.1 reads BOM-less files as ANSI).
#   * No double-quote character anywhere (5.1 mangles embedded double quotes in
#     arguments passed to native programs); every string is single-quoted.
#   * Everything is inside Install-BenchNotes, called on the last line.

function Install-BenchNotes {
    $ErrorActionPreference = 'Stop'
    $ProgressPreference = 'SilentlyContinue'
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    $clock = [Diagnostics.Stopwatch]::StartNew()

    $localAppData = $env:LOCALAPPDATA
    if (-not $localAppData) { $localAppData = Join-Path $env:USERPROFILE 'AppData\Local' }
    $homeDir = $env:BENCHNOTES_HOME
    if (-not $homeDir) { $homeDir = Join-Path $localAppData 'BenchNotes\bshell-node-home' }
    $appsDir = $env:BENCHNOTES_APPS_DIR
    if (-not $appsDir) { $appsDir = [Environment]::GetFolderPath('Programs') }
    $tarball = $env:BENCHNOTES_TARBALL
    if (-not $tarball) { $tarball = 'benchnotes' }
    $nodeWant = $env:BENCHNOTES_NODE_VERSION
    if (-not $nodeWant) { $nodeWant = '24.22.1' }
    $distUrl = $env:BENCHNOTES_NODE_DIST_URL
    if (-not $distUrl) { $distUrl = 'https://nodejs.org/dist' }
    $skipBackend = ($env:BENCHNOTES_SKIP_BACKEND_CHECK -eq '1')

    New-Item -ItemType Directory -Force -Path (Join-Path $homeDir 'logs') | Out-Null
    $logFile = Join-Path $homeDir 'logs\install.log'
    Set-Content -Path $logFile -Value '' -Encoding Ascii
    $tmpDir = Join-Path ([IO.Path]::GetTempPath()) ('benchnotes-install-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null

    function Write-Log {
        param([string]$Message)
        Write-Host $Message
        Add-Content -Path $logFile -Value $Message
    }

    function Invoke-Native {
        param([string]$What, [string]$Exe, [string[]]$Arguments)
        Write-Log ('-> ' + $What)
        $saved = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            & $Exe @Arguments 2>&1 | ForEach-Object { Add-Content -Path $logFile -Value $_.ToString() }
            $code = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $saved
        }
        if ($code -ne 0) { throw ($What + ' failed with exit code ' + $code) }
    }

    # Usable means major version 24 or later with npm.cmd next to node.exe.
    function Test-NodeOk {
        param([string]$NodeExe)
        try {
            $major = (& $NodeExe -p 'process.versions.node.split(String.fromCharCode(46))[0]' 2>$null | Select-Object -First 1)
            if ([int]$major -lt 24) { return $false }
            return (Test-Path (Join-Path (Split-Path $NodeExe) 'npm.cmd'))
        }
        catch {
            return $false
        }
    }

    function Get-DirBytes {
        param([string]$Path)
        if (-not (Test-Path $Path)) { return 0 }
        $sum = (Get-ChildItem -Path $Path -Recurse -File -Force | Measure-Object -Property Length -Sum).Sum
        if ($sum) { return [int64]$sum }
        return 0
    }

    function New-Shortcut {
        param([string]$Path, [string]$Target, [string]$Arguments, [string]$Icon, [string]$WorkDir)
        $shell = New-Object -ComObject WScript.Shell
        $lnk = $shell.CreateShortcut($Path)
        $lnk.TargetPath = $Target
        $lnk.Arguments = $Arguments
        $lnk.WorkingDirectory = $WorkDir
        $lnk.WindowStyle = 7
        $lnk.Description = 'Bench Notes (bshell-node)'
        if (Test-Path $Icon) { $lnk.IconLocation = $Icon }
        $lnk.Save()
    }

    try {
        # ---- 1. Node.js ----------------------------------------------------
        $nodeExe = $null
        $runtimeDownloaded = 'no'
        if ($env:BENCHNOTES_FORCE_RUNTIME_INSTALL -ne '1') {
            $found = Get-Command node -ErrorAction SilentlyContinue
            if ($found -and (Test-NodeOk $found.Source)) { $nodeExe = $found.Source }
        }
        if ($nodeExe) {
            Write-Log ('Using Node.js at ' + $nodeExe)
        }
        else {
            Write-Log ('No usable Node.js 24+ found (or forced); downloading Node.js ' + $nodeWant + ' under ' + $homeDir)
            $arch = 'x64'
            if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { $arch = 'arm64' }
            $name = 'node-v' + $nodeWant + '-win-' + $arch + '.zip'
            $sums = Join-Path $tmpDir 'SHASUMS256.txt'
            $zip = Join-Path $tmpDir $name
            Write-Log '-> download Node.js checksums'
            Invoke-WebRequest -UseBasicParsing -Uri ($distUrl + '/v' + $nodeWant + '/SHASUMS256.txt') -OutFile $sums
            Write-Log ('-> download Node.js ' + $nodeWant)
            Invoke-WebRequest -UseBasicParsing -Uri ($distUrl + '/v' + $nodeWant + '/' + $name) -OutFile $zip
            Write-Log ('fetched: node-runtime ' + (Get-Item $zip).Length + ' bytes')
            $line = Get-Content $sums | Where-Object { $_.EndsWith(' ' + $name) } | Select-Object -First 1
            if (-not $line) { throw ('no checksum listed for ' + $name) }
            $expected = $line.Split(' ')[0].ToLower()
            $actual = (Get-FileHash -Algorithm SHA256 -Path $zip).Hash.ToLower()
            if ($actual -ne $expected) { throw ('checksum mismatch for ' + $name) }
            $unpack = Join-Path $tmpDir 'node-unpack'
            Expand-Archive -Path $zip -DestinationPath $unpack -Force
            $nodeHome = Join-Path $homeDir 'node'
            if (Test-Path $nodeHome) { Remove-Item -Recurse -Force $nodeHome }
            Move-Item -Path (Join-Path $unpack ('node-v' + $nodeWant + '-win-' + $arch)) -Destination $nodeHome
            $nodeExe = Join-Path $nodeHome 'node.exe'
            if (-not (Test-NodeOk $nodeExe)) { throw ('downloaded Node.js is not usable: ' + $nodeExe) }
            $runtimeDownloaded = 'yes'
            Write-Log ('Installed Node.js at ' + $nodeExe)
        }
        $nodeDir = Split-Path $nodeExe
        $npmCmd = Join-Path $nodeDir 'npm.cmd'
        $env:PATH = $nodeDir + ';' + $env:PATH

        # ---- 2. install the package -----------------------------------------
        $npmCache = Join-Path $homeDir 'cache\npm'
        if ($tarball -match '^https?://') {
            $tgz = Join-Path $tmpDir ([IO.Path]::GetFileName(([Uri]$tarball).AbsolutePath))
            Write-Log '-> download tarball'
            Invoke-WebRequest -UseBasicParsing -Uri $tarball -OutFile $tgz
            Write-Log ('fetched: tarball ' + (Get-Item $tgz).Length + ' bytes')
            $tarball = $tgz
        }
        Invoke-Native ('npm install ' + $tarball) $npmCmd @('install', '--prefix', $homeDir, '--cache', $npmCache, '--no-audit', '--no-fund', '--no-progress', $tarball)
        Write-Log ('fetched: npm downloads about ' + (Get-DirBytes $npmCache) + ' bytes (npm cache size, cache removed below)')
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $npmCache
        $pkgDir = Join-Path $homeDir 'node_modules\benchnotes'
        if (-not (Test-Path (Join-Path $pkgDir 'bin\benchnotes.js'))) { throw ('npm did not install benchnotes under ' + $homeDir) }

        # ---- 3. native shell: Start menu shortcut ----------------------------
        # Relative script path + WorkingDirectory keeps the shortcut arguments free of quotes and spaces.
        $iconSource = Join-Path $pkgDir 'icon.ico'
        $icon = Join-Path $homeDir 'icon.ico'
        if (Test-Path $iconSource) { Copy-Item -Force $iconSource $icon }
        New-Item -ItemType Directory -Force -Path $appsDir | Out-Null
        $lnkPath = Join-Path $appsDir 'Bench Notes (bshell-node).lnk'
        New-Shortcut -Path $lnkPath -Target $nodeExe -Arguments 'bin\benchnotes.js ui --detach' -Icon $icon -WorkDir $pkgDir
        $readBack = (New-Object -ComObject WScript.Shell).CreateShortcut($lnkPath)
        # Compare files, not strings: Windows may store the long form of a path given in 8.3 form.
        $fso = New-Object -ComObject Scripting.FileSystemObject
        if (-not $fso.FileExists($readBack.TargetPath)) { throw 'shortcut verification failed' }
        if ($fso.GetFile($readBack.TargetPath).ShortPath -ne $fso.GetFile($nodeExe).ShortPath) { throw 'shortcut verification failed' }
        Write-Log ('shortcut: ' + $lnkPath)

        # ---- 4. self-test ----------------------------------------------------
        $checkArgs = @('bin\benchnotes.js', 'ui', '--check')
        if ($skipBackend) { $checkArgs += '--skip-backend' }
        Push-Location $pkgDir
        try { Invoke-Native 'self-test' $nodeExe $checkArgs } finally { Pop-Location }

        Write-Log ('runtime_downloaded: ' + $runtimeDownloaded)
        Write-Log ('install_seconds: ' + [int]$clock.Elapsed.TotalSeconds)
        Write-Log ('prefix: ' + $homeDir)
        Write-Log ('interpreter: ' + $nodeExe)
        Write-Log ('cli: ' + (Join-Path $pkgDir 'bin\benchnotes.js'))
        Write-Log ('app: ' + $lnkPath)
        Write-Log 'Done.'
    }
    catch {
        Write-Log ('ERROR: ' + $_.Exception.Message)
        Write-Log ('Details are in ' + $logFile)
        throw
    }
    finally {
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $tmpDir
    }
}

Install-BenchNotes
