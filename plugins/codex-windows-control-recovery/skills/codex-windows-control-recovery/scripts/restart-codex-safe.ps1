[CmdletBinding()]
param(
    [switch]$PreflightOnly,
    [switch]$ScheduleRestart,
    [ValidateRange(2, 60)]
    [int]$DelaySeconds = 8
)

$ErrorActionPreference = 'Stop'
if (-not $PreflightOnly -and -not $ScheduleRestart) {
    throw 'Choose -PreflightOnly or -ScheduleRestart explicitly.'
}
if ($PreflightOnly -and $ScheduleRestart) {
    throw 'Choose only one mode.'
}

$package = Get-AppxPackage |
    Where-Object {
        $_.Name -match '(^|\.)Codex$|OpenAI\.Codex' -or
        $_.PackageFamilyName -match 'OpenAI\.Codex'
    } |
    Sort-Object Version -Descending |
    Select-Object -First 1
if (-not $package -or -not $package.InstallLocation) {
    throw 'No registered Codex AppX package with an install location was found.'
}

$installRoot = [IO.Path]::GetFullPath($package.InstallLocation).TrimEnd('\')
$targets = @(
    Get-CimInstance Win32_Process |
        Where-Object {
            $_.ExecutablePath -and
            $_.ExecutablePath.StartsWith($installRoot + '\', [StringComparison]::OrdinalIgnoreCase)
        } |
        Select-Object ProcessId, Name, ExecutablePath
)

if ($targets.Count -eq 0) {
    throw "No running process was found under the registered install root: $installRoot"
}

Write-Output "Package: $($package.PackageFullName)"
Write-Output "Install root: $installRoot"
Write-Output 'Processes selected by executable-path containment:'
$targets | Format-Table -AutoSize | Out-String | Write-Output

if ($PreflightOnly) {
    Write-Output 'Preflight complete. No process was stopped.'
    exit 0
}

$manifest = Get-AppxPackageManifest -Package $package.PackageFullName
$appId = @($manifest.Package.Applications.Application)[0].Id
if (-not $appId) {
    throw 'Could not resolve the registered application identity.'
}
$aumid = "$($package.PackageFamilyName)!$appId"
$pids = @($targets.ProcessId)

$template = @'
Start-Sleep -Seconds __DELAY__
$allowed = @(__PIDS__)
foreach ($processId in $allowed) {
    try { Stop-Process -Id $processId -Force -ErrorAction Stop } catch { }
}
Start-Sleep -Seconds 2
Start-Process -FilePath 'explorer.exe' -ArgumentList 'shell:AppsFolder\__AUMID__'
'@
$restartScript = $template.
    Replace('__DELAY__', [string]$DelaySeconds).
    Replace('__PIDS__', ($pids -join ',')).
    Replace('__AUMID__', $aumid)

$bytes = [Text.Encoding]::Unicode.GetBytes($restartScript)
$encoded = [Convert]::ToBase64String($bytes)
Start-Process -FilePath 'powershell.exe' -ArgumentList @(
    '-NoLogo',
    '-NoProfile',
    '-NonInteractive',
    '-WindowStyle',
    'Hidden',
    '-EncodedCommand',
    $encoded
) -WindowStyle Hidden

Write-Output "A scoped restart was scheduled in $DelaySeconds seconds. Save work immediately."
