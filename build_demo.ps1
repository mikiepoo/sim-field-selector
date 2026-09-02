param(
    [string]$ReplayUrl = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path $PSScriptRoot).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$BuildRoot = Join-Path $ProjectRoot "build"
$DistRoot = Join-Path $ProjectRoot "dist"
$ReleaseRoot = Join-Path $ProjectRoot "release"
$DemoConfigRoot = Join-Path $BuildRoot "demo_config"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "The project virtual environment is missing: $Python"
}
function Reset-ProjectDirectory([string]$Target) {
    $fullTarget = [System.IO.Path]::GetFullPath($Target)
    $rootPrefix = $ProjectRoot.TrimEnd('\') + '\'
    if (-not $fullTarget.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to reset a directory outside the project: $fullTarget"
    }
    if (Test-Path -LiteralPath $fullTarget) {
        Remove-Item -LiteralPath $fullTarget -Recurse -Force
    }
    New-Item -ItemType Directory -Path $fullTarget | Out-Null
}

Reset-ProjectDirectory $BuildRoot
Reset-ProjectDirectory $DistRoot
Reset-ProjectDirectory $ReleaseRoot
New-Item -ItemType Directory -Path $DemoConfigRoot | Out-Null

$PrivateUrlFile = Join-Path $ProjectRoot ".demo-replay-url"
if (-not $ReplayUrl -and (Test-Path -LiteralPath $PrivateUrlFile)) {
    $ReplayUrl = (Get-Content -LiteralPath $PrivateUrlFile -Raw).Trim()
}
if (-not $ReplayUrl) {
    Write-Warning "No replay URL was supplied. The installer will work, but its demo replay download button will be disabled."
} else {
    $ParsedReplayUrl = $null
    if (-not [Uri]::TryCreate($ReplayUrl, [UriKind]::Absolute, [ref]$ParsedReplayUrl) -or
        $ParsedReplayUrl.Scheme -ne "https" -or
        $ParsedReplayUrl.Host -notin @("estesl2l.com", "www.estesl2l.com")) {
        throw "ReplayUrl must be an HTTPS URL hosted on estesl2l.com."
    }
}
$BlankReplayConfig = @{ url = "" } | ConvertTo-Json
Set-Content -LiteralPath (Join-Path $DemoConfigRoot "demo_replay.json") -Value $BlankReplayConfig -Encoding utf8
$PrivateReplayConfig = @{ url = $ReplayUrl } | ConvertTo-Json
Set-Content -LiteralPath (Join-Path $DemoConfigRoot "demo_replay_private.json") -Value $PrivateReplayConfig -Encoding utf8
$DemoAvailable = if ($ReplayUrl) { 1 } else { 0 }
Set-Content -LiteralPath (Join-Path $DemoConfigRoot "installer_defines.iss") -Value "#define DemoAvailable $DemoAvailable" -Encoding ascii

& $Python -m PyInstaller --noconfirm --clean (Join-Path $ProjectRoot "SimFieldSelector.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

$InnoCandidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
)
$InnoCompiler = $InnoCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if (-not $InnoCompiler) {
    throw "Inno Setup 6 was not found. The portable app is ready under dist\SimFieldSelector, but the installer was not built."
}

& $InnoCompiler (Join-Path $ProjectRoot "packaging\installer.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed with exit code $LASTEXITCODE" }

$Installer = Join-Path $ReleaseRoot "SimFieldSelectorSetup.exe"
$Hash = Get-FileHash -Algorithm SHA256 -LiteralPath $Installer
$ChecksumPath = Join-Path $ReleaseRoot "SHA256SUMS.txt"
Set-Content -LiteralPath $ChecksumPath -Value "$($Hash.Hash)  SimFieldSelectorSetup.exe" -Encoding ascii
Write-Host "Installer: $Installer"
Write-Host "SHA256: $($Hash.Hash)"
Write-Host "Replay auto-download configured: $([bool]$ReplayUrl)"
