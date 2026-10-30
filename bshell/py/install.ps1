# Bench Notes (bshell-py) installer for Windows. PowerShell 5.1 or later.
#
#   irm <url>/install.ps1 | iex
#
# Per user, no administrator rights:
#   1. find Python 3.11+ (or install a private one with uv)
#   2. create a private venv under BENCHNOTES_HOME
#   3. pip install the benchnotes wheel (and pywebview) into it
#   4. create a Start menu shortcut to the venv pythonw.exe
#   5. run the self-test (benchnotes ui --check)
#
# Environment overrides (all optional):
#   BENCHNOTES_HOME                   install root         (default %LOCALAPPDATA%\BenchNotes\bshell-py-home)
#   BENCHNOTES_APPS_DIR               shortcut folder      (default: your Start menu Programs folder)
#   BENCHNOTES_WHEEL                  local wheel path or URL (default: benchnotes from the package index)
#   BENCHNOTES_PYTHON_VERSION         Python installed by uv  (default 3.12)
#   BENCHNOTES_FORCE_RUNTIME_INSTALL  1 = ignore any Python found, install one
#   BENCHNOTES_UV_INSTALLER_URL       uv installer location   (default https://astral.sh/uv/install.ps1)
#   BENCHNOTES_SKIP_BACKEND_CHECK     1 = self-test without a window backend (CI only)
#
# House rules for this file, checked by bench/tests/test_install_ps1.py:
#   * ASCII only (Windows PowerShell 5.1 reads BOM-less files as ANSI).
#   * No double-quote character anywhere. Windows PowerShell 5.1 mangles
#     embedded double quotes in arguments passed to native programs, so every
#     string here is single-quoted and arguments never need quoting.
#   * Everything is inside Install-BenchNotes, called on the last line, so a
#     truncated download cannot run half a script.

function Install-BenchNotes {
    $ErrorActionPreference = 'Stop'
    $ProgressPreference = 'SilentlyContinue'
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    $clock = [Diagnostics.Stopwatch]::StartNew()

    $localAppData = $env:LOCALAPPDATA
    if (-not $localAppData) { $localAppData = Join-Path $env:USERPROFILE 'AppData\Local' }
    $homeDir = $env:BENCHNOTES_HOME
    if (-not $homeDir) { $homeDir = Join-Path $localAppData 'BenchNotes\bshell-py-home' }
    $appsDir = $env:BENCHNOTES_APPS_DIR
    if (-not $appsDir) { $appsDir = [Environment]::GetFolderPath('Programs') }
    $wheel = $env:BENCHNOTES_WHEEL
    if (-not $wheel) { $wheel = 'benchnotes' }
    $pyWant = $env:BENCHNOTES_PYTHON_VERSION
    if (-not $pyWant) { $pyWant = '3.12' }
    $uvUrl = $env:BENCHNOTES_UV_INSTALLER_URL
    if (-not $uvUrl) { $uvUrl = 'https://astral.sh/uv/install.ps1' }
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

    # Run a native program with output going to the log file.
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

    # Usable means 3.11+ with venv and ensurepip. Prints the interpreter path.
    function Get-PythonPath {
        param([string]$Exe, [string[]]$Prefix)
        try {
            $check = $Prefix + @('-c', 'import sys,venv,ensurepip;sys.exit(0 if sys.version_info>=(3,11) else 1)')
            & $Exe @check 2>$null | Out-Null
            if ($LASTEXITCODE -ne 0) { return $null }
            $show = $Prefix + @('-c', 'import sys;print(sys.executable)')
            $path = (& $Exe @show 2>$null | Select-Object -First 1)
            if (-not $path) { return $null }
            # Microsoft Store python lives under WindowsApps and misbehaves in venvs.
            if ($path -like '*\WindowsApps\*') { return $null }
            return [string]$path
        }
        catch {
            return $null
        }
    }

    function Find-Python {
        $tries = @(
            @{ Exe = 'py'; Prefix = @('-3.13') },
            @{ Exe = 'py'; Prefix = @('-3.12') },
            @{ Exe = 'py'; Prefix = @('-3.11') },
            @{ Exe = 'python'; Prefix = @() },
            @{ Exe = 'python3'; Prefix = @() }
        )
        foreach ($t in $tries) {
            if (-not (Get-Command $t.Exe -ErrorAction SilentlyContinue)) { continue }
            $found = Get-PythonPath -Exe $t.Exe -Prefix $t.Prefix
            if ($found) { return $found }
        }
        return $null
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
        $lnk.Description = 'Bench Notes (bshell-py)'
        if (Test-Path $Icon) { $lnk.IconLocation = $Icon }
        $lnk.Save()
    }

    try {
        # ---- 1. Python ----------------------------------------------------
        $pythonExe = $null
        $runtimeDownloaded = 'no'
        if ($env:BENCHNOTES_FORCE_RUNTIME_INSTALL -ne '1') { $pythonExe = Find-Python }
        if ($pythonExe) {
            Write-Log ('Using Python at ' + $pythonExe)
        }
        else {
            Write-Log ('No usable Python 3.11+ found (or forced); installing Python ' + $pyWant + ' with uv under ' + $homeDir)
            $uvDir = Join-Path $homeDir 'uv'
            $installer = Join-Path $tmpDir 'uv-installer.ps1'
            # Download to a file first, so a dropped connection cannot execute half a script.
            Write-Log '-> download uv installer'
            Invoke-WebRequest -UseBasicParsing -Uri $uvUrl -OutFile $installer
            Write-Log ('fetched: uv-installer ' + (Get-Item $installer).Length + ' bytes')
            $env:UV_UNMANAGED_INSTALL = $uvDir
            $env:UV_INSTALL_DIR = $uvDir
            $env:UV_NO_MODIFY_PATH = '1'
            Invoke-Native 'run uv installer' 'powershell' @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $installer)
            $uvExe = $null
            foreach ($c in @((Join-Path $uvDir 'uv.exe'), (Join-Path $uvDir 'bin\uv.exe'))) {
                if (Test-Path $c) { $uvExe = $c; break }
            }
            if (-not $uvExe) { throw ('uv installer did not produce uv.exe under ' + $uvDir) }
            $env:UV_PYTHON_INSTALL_DIR = Join-Path $homeDir 'python'
            $env:UV_CACHE_DIR = Join-Path $homeDir 'cache\uv'
            $env:UV_PYTHON_INSTALL_BIN = '0'
            $env:UV_PYTHON_INSTALL_REGISTRY = '0'
            Invoke-Native ('install Python ' + $pyWant) $uvExe @('python', 'install', $pyWant)
            $pythonExe = (& $uvExe python find $pyWant | Select-Object -First 1)
            if (-not $pythonExe) { throw 'uv could not find the Python it just installed' }
            $runtimeDownloaded = 'yes'
            Write-Log ('Installed Python at ' + $pythonExe)
        }

        # ---- 2. private venv ------------------------------------------------
        $venv = Join-Path $homeDir 'venv'
        Invoke-Native 'create venv' $pythonExe @('-m', 'venv', '--clear', $venv)
        $venvPython = Join-Path $venv 'Scripts\python.exe'
        $venvPythonw = Join-Path $venv 'Scripts\pythonw.exe'

        # ---- 3. install the package ----------------------------------------
        $env:PIP_CACHE_DIR = Join-Path $homeDir 'cache\pip'
        $env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
        $env:PIP_NO_INPUT = '1'
        if ($wheel -match '^https?://') {
            $wheelFile = Join-Path $tmpDir ([IO.Path]::GetFileName(([Uri]$wheel).AbsolutePath))
            Write-Log '-> download wheel'
            Invoke-WebRequest -UseBasicParsing -Uri $wheel -OutFile $wheelFile
            Write-Log ('fetched: wheel ' + (Get-Item $wheelFile).Length + ' bytes')
            $wheel = $wheelFile
        }
        Invoke-Native ('pip install ' + $wheel) $venvPython @('-m', 'pip', 'install', $wheel)
        $cacheBytes = Get-DirBytes $env:PIP_CACHE_DIR
        Write-Log ('fetched: pip downloads about ' + $cacheBytes + ' bytes (pip cache size, cache removed below)')
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $env:PIP_CACHE_DIR
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $homeDir 'cache\uv')

        # ---- 4. native shell: Start menu shortcut ---------------------------
        # The icon is copied out of site-packages so it survives upgrades.
        $iconSource = Join-Path $venv 'Lib\site-packages\benchnotes\icon.ico'
        $icon = Join-Path $homeDir 'icon.ico'
        if (Test-Path $iconSource) { Copy-Item -Force $iconSource $icon }
        New-Item -ItemType Directory -Force -Path $appsDir | Out-Null
        $lnkPath = Join-Path $appsDir 'Bench Notes (bshell-py).lnk'
        New-Shortcut -Path $lnkPath -Target $venvPythonw -Arguments '-m benchnotes ui' -Icon $icon -WorkDir $homeDir
        $readBack = (New-Object -ComObject WScript.Shell).CreateShortcut($lnkPath)
        # Compare files, not strings: Windows may store the long form of a path given in 8.3 form.
        $fso = New-Object -ComObject Scripting.FileSystemObject
        if (-not $fso.FileExists($readBack.TargetPath)) { throw 'shortcut verification failed' }
        if ($fso.GetFile($readBack.TargetPath).ShortPath -ne $fso.GetFile($venvPythonw).ShortPath) { throw 'shortcut verification failed' }
        Write-Log ('shortcut: ' + $lnkPath)

        # ---- 5. self-test ---------------------------------------------------
        $checkArgs = @('-m', 'benchnotes', 'ui', '--check')
        if ($skipBackend) { $checkArgs += '--skip-backend' }
        Invoke-Native 'self-test' $venvPython $checkArgs
        # The same check through pythonw, which is what the shortcut runs.
        $pwArgs = '-m benchnotes ui --check'
        if ($skipBackend) { $pwArgs += ' --skip-backend' }
        $proc = Start-Process -FilePath $venvPythonw -ArgumentList $pwArgs -Wait -PassThru -WindowStyle Hidden
        if ($proc.ExitCode -ne 0) { throw ('pythonw self-test failed with exit code ' + $proc.ExitCode) }

        Write-Log ('runtime_downloaded: ' + $runtimeDownloaded)
        Write-Log ('install_seconds: ' + [int]$clock.Elapsed.TotalSeconds)
        Write-Log ('venv: ' + $venv)
        Write-Log ('interpreter: ' + $venvPython)
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
