[CmdletBinding()]
param(
    [string]$Destination,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$version = '3.0.3'
$expectedSha256 = 'DBF930B076C6B9BE08D57C449CACEFC3BDD6B71EBD59B3066FC0E1F5B14F9423'
$url = "https://github.com/iBotPeaches/Apktool/releases/download/v$version/apktool_$version.jar"
if (-not $Destination) { $Destination = Join-Path $PSScriptRoot ".tools\apktool_$version.jar" }
$destinationPath = [IO.Path]::GetFullPath($Destination)

if ((Test-Path -LiteralPath $destinationPath) -and -not $Force) {
    $currentHash = (Get-FileHash -LiteralPath $destinationPath -Algorithm SHA256).Hash
    if ($currentHash -eq $expectedSha256) {
        Write-Host "Apktool $version already installed and verified: $destinationPath"
        exit 0
    }
    throw "Existing Apktool hash mismatch at $destinationPath. Use -Force to replace it."
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destinationPath) | Out-Null
$temporary = "$destinationPath.download"
try {
    Invoke-WebRequest -Uri $url -OutFile $temporary
    $actualHash = (Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash
    if ($actualHash -ne $expectedSha256) {
        throw "Downloaded Apktool hash mismatch. Expected $expectedSha256, found $actualHash."
    }
    Move-Item -LiteralPath $temporary -Destination $destinationPath -Force
} finally {
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
}

Write-Host "Installed Apktool $version: $destinationPath"
Write-Host "SHA-256: $expectedSha256"
