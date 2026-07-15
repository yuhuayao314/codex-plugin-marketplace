[CmdletBinding()]
param(
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'

function Get-Sha256OrNull {
    param([string]$LiteralPath)
    if (-not (Test-Path -LiteralPath $LiteralPath -PathType Leaf)) {
        return $null
    }
    return (Get-FileHash -LiteralPath $LiteralPath -Algorithm SHA256).Hash
}

function Get-ConfigPipeEntries {
    $configPath = Join-Path $env:USERPROFILE '.codex\config.toml'
    if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
        return @()
    }
    return @(
        Get-Content -LiteralPath $configPath |
            Where-Object { $_ -match '^\s*(SKY_CUA_NATIVE_PIPE|SKY_CUA_NATIVE_PIPE_DIRECTORY)\s*=' }
    )
}

$packages = @(
    Get-AppxPackage |
        Where-Object {
            $_.Name -match '(^|\.)Codex$|OpenAI\.Codex' -or
            $_.PackageFamilyName -match 'OpenAI\.Codex'
        } |
        Select-Object Name, PackageFullName, Version, InstallLocation, Status
)

$installRoots = @(
    $packages |
        Where-Object { $_.InstallLocation } |
        ForEach-Object { [IO.Path]::GetFullPath($_.InstallLocation).TrimEnd('\') }
)

$processes = @(
    Get-CimInstance Win32_Process |
        Where-Object {
            if (-not $_.ExecutablePath -or $installRoots.Count -eq 0) {
                return $false
            }
            $executablePath = $_.ExecutablePath
            return @(
                $installRoots |
                    Where-Object {
                        $executablePath.StartsWith($_ + '\', [StringComparison]::OrdinalIgnoreCase)
                    }
            ).Count -gt 0
        } |
        Select-Object ProcessId, Name, ExecutablePath, CommandLine
)

$runtimeRoots = @(
    Join-Path $env:USERPROFILE '.codex'
    Join-Path $env:LOCALAPPDATA 'Codex'
) | Select-Object -Unique

$runtimeCandidates = @()
foreach ($root in $runtimeRoots) {
    if (-not (Test-Path -LiteralPath $root -PathType Container)) {
        continue
    }
    $runtimeCandidates += @(
        Get-ChildItem -LiteralPath $root -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '(node|computer|cua|codex).*\.(exe|js|mjs)$' } |
            Select-Object -First 100 |
            ForEach-Object {
                [pscustomobject]@{
                    Path = $_.FullName
                    Length = $_.Length
                    LastWriteTimeUtc = $_.LastWriteTimeUtc
                    Sha256 = Get-Sha256OrNull -LiteralPath $_.FullName
                }
            }
    )
}

$pipeNames = @()
try {
    $pipeNames = @(
        Get-ChildItem -LiteralPath '\\.\pipe\' -ErrorAction Stop |
            Where-Object { $_.Name -match '(codex|cua|computer)' } |
            Select-Object -ExpandProperty Name
    )
} catch {
    $pipeNames = @()
}

$report = [ordered]@{
    generatedAtUtc = [DateTime]::UtcNow.ToString('o')
    computerName = $env:COMPUTERNAME
    powershellVersion = $PSVersionTable.PSVersion.ToString()
    packages = $packages
    packageScopedProcesses = $processes
    stalePipeConfigEntries = @(Get-ConfigPipeEntries)
    matchingNamedPipes = $pipeNames
    runtimeCandidates = $runtimeCandidates
    notes = @(
        'This report is read-only.'
        'Absence of a tool in a task schema cannot be proven from PowerShell; verify inside a fresh Codex task after restart.'
        'This diagnostic is scoped only to Windows Computer Use.'
    )
}

$json = $report | ConvertTo-Json -Depth 8
if ($OutputPath) {
    $fullOutput = [IO.Path]::GetFullPath($OutputPath)
    $parent = Split-Path -Parent $fullOutput
    if ($parent -and -not (Test-Path -LiteralPath $parent -PathType Container)) {
        New-Item -ItemType Directory -Path $parent | Out-Null
    }
    [IO.File]::WriteAllText($fullOutput, $json, [Text.UTF8Encoding]::new($false))
}
$json
