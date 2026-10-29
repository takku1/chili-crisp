param([string]$Distribution = 'Ubuntu-26.04')
$ErrorActionPreference = 'Stop'

# Run this from an ordinary Windows PowerShell session. The managed agent
# session may be denied access to the WSL service before Linux starts.
& wsl.exe --distribution $Distribution --user root --exec /bin/true
if ($LASTEXITCODE -ne 0) {
    throw 'WSL cannot start from this session. No Linux setup was attempted. Run this script from an ordinary terminal or an authorized WSL-enabled agent session.'
}
$scriptPath = Join-Path $PSScriptRoot 'setup-linux.sh'
$scriptBytes = [Text.Encoding]::UTF8.GetBytes(([IO.File]::ReadAllText($scriptPath)).Replace("`r`n", "`n"))
$scriptBase64 = [Convert]::ToBase64String($scriptBytes)
$linuxCommand = "printf %s $scriptBase64 | base64 --decode | bash"
& wsl.exe --distribution $Distribution --user root -- bash -lc $linuxCommand
if ($LASTEXITCODE -eq 20) {
    Write-Output "Systemd is configured. Save any work running in $Distribution, then run:"
    Write-Output "  wsl --terminate $Distribution"
    Write-Output "  & '$PSCommandPath' -Distribution '$Distribution'"
    Write-Output 'Only the selected Ubuntu distribution needs restarting; no global WSL shutdown is required.'
    return
}
if ($LASTEXITCODE -ne 0) { throw 'Linux prerequisite setup failed; inspect the output above.' }
Write-Output 'Linux prerequisites prepared. Native fixtures, rootfs preparation and measured frontier still need to run.'
