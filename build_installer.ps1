$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path $PSScriptRoot).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$BuildRoot = Join-Path $ProjectRoot "build"
$DistRoot = Join-Path $ProjectRoot "dist"
$ReleaseRoot = Join-Path $ProjectRoot "release"

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
