[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SourcePath,

    [Parameter(Mandatory = $true)]
    [string]$TargetPath,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Fa-f0-9]{64}$')]
    [string]$ExpectedSha256,

    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath($SourcePath)
$target = [IO.Path]::GetFullPath($TargetPath)
$windowsApps = [IO.Path]::GetFullPath((Join-Path $env:ProgramFiles 'WindowsApps')).TrimEnd('\') + '\'

if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
    throw "Source file not found: $source"
}
if ($target.StartsWith($windowsApps, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Refusing to write inside WindowsApps.'
}

$actualSourceHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
if ($actualSourceHash -ne $ExpectedSha256.ToUpperInvariant()) {
    throw "Source SHA256 mismatch. Expected $ExpectedSha256, found $actualSourceHash"
}

Write-Output "Source: $source"
Write-Output "Target: $target"
Write-Output "Verified SHA256: $actualSourceHash"

if (-not $Apply) {
    Write-Output 'Preview only. Re-run with -Apply after confirming the source belongs to the exact installed Codex build.'
    exit 0
}

$targetParent = Split-Path -Parent $target
if (-not (Test-Path -LiteralPath $targetParent -PathType Container)) {
    New-Item -ItemType Directory -Path $targetParent | Out-Null
}

$staging = Join-Path $targetParent ('.runtime-staging-' + [Guid]::NewGuid().ToString('N'))
Copy-Item -LiteralPath $source -Destination $staging -ErrorAction Stop
$stagingHash = (Get-FileHash -LiteralPath $staging -Algorithm SHA256).Hash
if ($stagingHash -ne $actualSourceHash) {
    Remove-Item -LiteralPath $staging -Force
    throw 'Staging SHA256 mismatch. Target was not changed.'
}

$backup = $null
if (Test-Path -LiteralPath $target -PathType Leaf) {
    $backup = "$target.backup-$([DateTime]::UtcNow.ToString('yyyyMMddHHmmss'))"
    Copy-Item -LiteralPath $target -Destination $backup -ErrorAction Stop
}

try {
    Move-Item -LiteralPath $staging -Destination $target -Force
    $targetHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
    if ($targetHash -ne $actualSourceHash) {
        throw 'Target SHA256 mismatch after replacement.'
    }
} catch {
    if ($backup -and (Test-Path -LiteralPath $backup -PathType Leaf)) {
        Copy-Item -LiteralPath $backup -Destination $target -Force
    }
    if (Test-Path -LiteralPath $staging -PathType Leaf) {
        Remove-Item -LiteralPath $staging -Force
    }
    throw
}

Write-Output "Runtime repaired and verified: $target"
if ($backup) {
    Write-Output "Backup: $backup"
}
