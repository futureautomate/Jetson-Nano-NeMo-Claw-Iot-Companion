<#
.SYNOPSIS
    Sync this repo onto the Jetson Nano over SSH (one-way: Windows -> Jetson).

.DESCRIPTION
    Uses `rsync` if available (native, or via WSL) for a fast incremental sync.
    Otherwise falls back to packing a tarball with the built-in tar.exe, scp'ing
    it, and extracting it on the device. Either way the result is the same:
    jetson:~/jetson-companion/ becomes a mirror of this folder (minus .git, venvs,
    caches). Runtime state lives separately in ~/jetson-companion-data/ and is
    never touched.

.PARAMETER Run
    After syncing, launch the app on the Jetson:  python3 -m src.main

.PARAMETER Clean
    Delete ~/jetson-companion on the Jetson before copying (so files you deleted
    locally also disappear there). Implied when rsync is unavailable.

.PARAMETER RemoteHost
    SSH host alias (default: jetson — see ~/.ssh/config).

.EXAMPLE
    ./deploy.ps1
    ./deploy.ps1 -Run
    ./deploy.ps1 -Clean -Run
#>
[CmdletBinding()]
param(
    [switch]$Run,
    [switch]$Clean,
    [string]$RemoteHost = "jetson"
)

$ErrorActionPreference = "Stop"
$Repo       = $PSScriptRoot
$RemoteDir  = "~/jetson-companion"
$Excludes   = @(".git", "__pycache__", "*.pyc", ".venv", "venv", "env", ".vscode", ".idea", ".claude", "data", "*.log")

Write-Host "==> Deploying $Repo  ->  ${RemoteHost}:$RemoteDir" -ForegroundColor Cyan

# Resolve an rsync we can use (native, then WSL).
$rsyncCmd = $null
if (Get-Command rsync -ErrorAction SilentlyContinue) {
    $rsyncCmd = "rsync"
} elseif (Get-Command wsl.exe -ErrorAction SilentlyContinue) {
    & wsl.exe -e sh -c "command -v rsync" *> $null
    if ($LASTEXITCODE -eq 0) { $rsyncCmd = "wsl-rsync" }
}

if ($rsyncCmd) {
    $exArgs = $Excludes | ForEach-Object { "--exclude=$_" }
    $delete = if ($Clean) { @("--delete") } else { @() }
    if ($rsyncCmd -eq "wsl-rsync") {
        # Translate the Windows path to a /mnt/... path for WSL.
        $wslPath = (& wsl.exe -e wslpath -a "$Repo").Trim()
        & wsl.exe -e rsync -az @delete @exArgs "$wslPath/" "${RemoteHost}:$RemoteDir/"
    } else {
        & rsync -az @delete @exArgs "$Repo/" "${RemoteHost}:$RemoteDir/"
    }
    if ($LASTEXITCODE -ne 0) { throw "rsync failed ($LASTEXITCODE)" }
} else {
    Write-Host "    (no rsync found — using tar+scp; this always does a clean copy)" -ForegroundColor DarkGray
    $tar = Join-Path $env:SystemRoot "System32\tar.exe"
    if (-not (Test-Path $tar)) { throw "Need rsync or tar.exe; found neither." }
    $tmp = Join-Path $env:TEMP ("companion-deploy-{0}.tgz" -f ([guid]::NewGuid().ToString("N")))
    $exArgs = $Excludes | ForEach-Object { "--exclude=$_" }
    & $tar -czf $tmp -C $Repo @exArgs .
    if ($LASTEXITCODE -ne 0) { Remove-Item $tmp -ErrorAction SilentlyContinue; throw "tar failed ($LASTEXITCODE)" }
    try {
        & ssh $RemoteHost "rm -rf $RemoteDir && mkdir -p $RemoteDir ~/jetson-companion-data"
        & scp -q $tmp "${RemoteHost}:/tmp/companion-deploy.tgz"
        & ssh $RemoteHost "tar -xzf /tmp/companion-deploy.tgz -C $RemoteDir && rm -f /tmp/companion-deploy.tgz"
    } finally {
        Remove-Item $tmp -ErrorAction SilentlyContinue
    }
}

# Make sure the runtime data dir exists regardless of path taken.
& ssh $RemoteHost "mkdir -p ~/jetson-companion-data"
Write-Host "==> Synced." -ForegroundColor Green

if ($Run) {
    Write-Host "==> Running  python3 -m src.main  on $RemoteHost (Ctrl+C to stop)" -ForegroundColor Cyan
    & ssh -t $RemoteHost "cd $RemoteDir && python3 -m src.main"
}
