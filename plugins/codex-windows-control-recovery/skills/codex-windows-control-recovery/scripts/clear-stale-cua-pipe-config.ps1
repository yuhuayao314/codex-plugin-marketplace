[CmdletBinding()]
param(
    [string]$ConfigPath = (Join-Path $env:USERPROFILE '.codex\config.toml'),
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$fullConfig = [IO.Path]::GetFullPath($ConfigPath)
if (-not (Test-Path -LiteralPath $fullConfig -PathType Leaf)) {
    throw "Configuration file not found: $fullConfig"
}

$lines = [IO.File]::ReadAllLines($fullConfig)
$pattern = '^\s*(SKY_CUA_NATIVE_PIPE|SKY_CUA_NATIVE_PIPE_DIRECTORY)\s*='
$matches = @($lines | Where-Object { $_ -match $pattern })

if ($matches.Count -eq 0) {
    Write-Output 'No stale Computer Use pipe entries were found.'
    exit 0
}

Write-Output 'Exact entries selected for removal:'
$matches | ForEach-Object { Write-Output $_ }

if (-not $Apply) {
    Write-Output 'Preview only. Re-run with -Apply to remove only these entries.'
    exit 0
}

$kept = @($lines | Where-Object { $_ -notmatch $pattern })
$backup = "$fullConfig.cua-pipe-backup-$([DateTime]::UtcNow.ToString('yyyyMMddHHmmss'))"
Copy-Item -LiteralPath $fullConfig -Destination $backup -ErrorAction Stop

$temp = "$fullConfig.cua-pipe-staging-$([Guid]::NewGuid().ToString('N'))"
[IO.File]::WriteAllLines($temp, $kept, [Text.UTF8Encoding]::new($false))
Move-Item -LiteralPath $temp -Destination $fullConfig -Force

$remaining = @([IO.File]::ReadAllLines($fullConfig) | Where-Object { $_ -match $pattern })
if ($remaining.Count -ne 0) {
    Copy-Item -LiteralPath $backup -Destination $fullConfig -Force
    throw 'Postcondition failed. The original configuration was restored.'
}

Write-Output "Removed $($matches.Count) stale entries. Backup: $backup"
