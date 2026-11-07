<#
 LocalVault installer for Windows.
   .\install.ps1              install or update
   .\install.ps1 -Uninstall   remove the app (your vault is kept)
   .\install.ps1 -Uninstall -Purge   also delete your vault data
#>
param([switch]$Uninstall, [switch]$Purge)
$ErrorActionPreference = "Stop"

$RepoDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir   = Join-Path $env:LOCALAPPDATA "LocalVault-app"
$DataDir  = Join-Path $env:APPDATA "LocalVault"
$Desktop  = [Environment]::GetFolderPath("Desktop")
$StartMenu = Join-Path ([Environment]::GetFolderPath("Programs")) "LocalVault.lnk"
$DesktopLnk = Join-Path $Desktop "LocalVault.lnk"

function Say($m)  { Write-Host "==> $m" -ForegroundColor Yellow }
function Ok($m)   { Write-Host "[ok] $m" -ForegroundColor Green }

if ($Uninstall) {
    Remove-Item -Recurse -Force $AppDir -ErrorAction SilentlyContinue
    Remove-Item -Force $StartMenu, $DesktopLnk -ErrorAction SilentlyContinue
    Ok "LocalVault removed."
    if ($Purge) { Remove-Item -Recurse -Force $DataDir -ErrorAction SilentlyContinue; Ok "Vault data deleted." }
    else { Say "Your vault in $DataDir was kept. Use -Purge to delete it too." }
    exit 0
}

function Find-Python {
    foreach ($candidate in @(@("py", "-3"), @("python"))) {
        $exe = $candidate[0]
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        $extra = @(); if ($candidate.Count -gt 1) { $extra = $candidate[1..($candidate.Count - 1)] }
        try {
            & $exe @extra -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 9) else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) { return ,($candidate) }
        } catch { }
    }
    return $null
}

$py = Find-Python
if (-not $py) {
    Say "Python 3.9+ with Tk was not found."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        $answer = Read-Host "Install Python 3.12 with winget now? [Y/n]"
        if ($answer -notmatch '^[Nn]') {
            winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements
            Write-Host "Python was installed. Close this window and run install.bat again." -ForegroundColor Cyan
            exit 0
        }
    }
    Write-Host "Install Python from https://www.python.org/downloads/ (keep 'tcl/tk and IDLE' ticked), then run install.bat again." -ForegroundColor Red
    exit 1
}
$pyExe = $py[0]; $pyArgs = @(); if ($py.Count -gt 1) { $pyArgs = $py[1..($py.Count - 1)] }
Ok "Python found"

New-Item -ItemType Directory -Force -Path $AppDir | Out-Null
$venv = Join-Path $AppDir "venv"
& $pyExe @pyArgs -m venv $venv
if ($LASTEXITCODE -ne 0) { throw "Could not create a virtual environment." }
$venvPy = Join-Path $venv "Scripts\python.exe"
$venvPyw = Join-Path $venv "Scripts\pythonw.exe"

Say "Installing LocalVault and its dependencies (needs internet once)"
& $venvPy -m pip install --quiet --upgrade pip
& $venvPy -m pip install --quiet --upgrade $RepoDir
if ($LASTEXITCODE -ne 0) { throw "pip install failed." }
Ok "Installed to $AppDir"

$shell = New-Object -ComObject WScript.Shell
foreach ($path in @($StartMenu, $DesktopLnk)) {
    $lnk = $shell.CreateShortcut($path)
    $lnk.TargetPath = $venvPyw
    $lnk.Arguments = "-m localvault"
    $lnk.WorkingDirectory = $env:USERPROFILE
    $lnk.Description = "LocalVault - offline password manager"
    $lnk.Save()
}
Ok "Desktop and Start Menu shortcuts created"
Say "Done. Open LocalVault from the Start Menu or your desktop."
