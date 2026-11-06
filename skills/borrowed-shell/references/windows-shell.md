# Windows shell: a Start-menu shortcut

No bundle is needed: the Start-menu `.lnk` gives the app a name and icon in Start and search; the window icon passed at runtime gives the taskbar its icon.

## Shortcut (PowerShell 5.1, ASCII, single quotes only)

```powershell
function New-Shortcut {
    param([string]$Path, [string]$Target, [string]$Arguments, [string]$Icon, [string]$WorkDir, [int]$WindowStyle = 1)
    $shell = New-Object -ComObject WScript.Shell
    $lnk = $shell.CreateShortcut($Path)
    $lnk.TargetPath = $Target
    $lnk.Arguments = $Arguments
    $lnk.WorkingDirectory = $WorkDir
    $lnk.WindowStyle = $WindowStyle            # 7 = minimised (use for node.exe)
    $lnk.Description = '<App Name>'
    if (Test-Path $Icon) { $lnk.IconLocation = $Icon }
    $lnk.Save()
}

$appsDir = [Environment]::GetFolderPath('Programs')          # per-user Start menu, no admin
$lnkPath = Join-Path $appsDir '<App Name>.lnk'
```

- **Python:** target `<venv>\Scripts\pythonw.exe`, arguments `-m <pkg> ui`. `pythonw` opens no console; the app must redirect `sys.stdout`/`sys.stderr` itself.
- **Node.js:** target `<runtime>\node.exe`, arguments `"<prefix>\node_modules\<pkg>\bin\<pkg>.js" ui`, `WindowStyle 7`. On start the app re-spawns itself detached and hidden (`windowsHide: true`) with output to a log file, then the parent exits.
- **Icon:** copy `icon.ico` out of the environment into the install home first, so a package upgrade cannot remove the file the shortcut points to.

## Verify the shortcut after creating it

Windows may store the long form of a path given in 8.3 form (`C:\Users\RUNNER~1\...`), so compare files, not strings:

```powershell
$readBack = (New-Object -ComObject WScript.Shell).CreateShortcut($lnkPath)
$fso = New-Object -ComObject Scripting.FileSystemObject
if (-not $fso.FileExists($readBack.TargetPath)) { throw 'shortcut verification failed' }
if ($fso.GetFile($readBack.TargetPath).ShortPath -ne $fso.GetFile($target).ShortPath) { throw 'shortcut verification failed' }
```

Then run the self-test **through the same executable the shortcut runs**:

```powershell
$proc = Start-Process -FilePath $venvPythonw -ArgumentList '-m <pkg> ui --check' -Wait -PassThru -WindowStyle Hidden
if ($proc.ExitCode -ne 0) { throw ('pythonw self-test failed with exit code ' + $proc.ExitCode) }
```

## Taskbar icon

Without an explicit window icon the taskbar shows `pythonw.exe`'s or `node.exe`'s icon even though the shortcut has yours.

- pywebview: `webview.start(icon=str(path_to_ico))` on Windows only.
- `@webviewjs/webview`: `createBrowserWindow({ ..., windowsTaskbarIcon: { data, width, height } })` and `win.setWindowIcon(data, width, height)` with raw RGBA bytes (ship a pre-converted `icon-64.rgba`).

## Not covered by the pattern

- Smart App Control and App Control for Business judge every native DLL loaded (pythonnet, the napi addon) on its own signature. Untested in the reference implementation; tell the user.
- Updating files while `pythonw` and the .NET bridge run is untested; prefer "update, then relaunch".
