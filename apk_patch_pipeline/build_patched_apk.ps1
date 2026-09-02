[CmdletBinding()]
param(
    [string]$SourceApk = 'base.apk',
    [string]$ProfilePath = 'apk_patch_pipeline\profiles\direct-server.local.json',
    [string]$OutputPath,
    [string]$ApktoolJar,
    [string]$AndroidSdkRoot,
    [string]$BuildToolsVersion,
    [string]$JavaPath,
    [string]$PythonPath,
    [string]$KeystorePath,
    [string]$KeyAlias = 'kickflight-local-test',
    [switch]$KeepWorkDirectory
)

$ErrorActionPreference = 'Stop'
$pipelineRoot = $PSScriptRoot
$repoRoot = Split-Path -Parent $pipelineRoot

function Resolve-RepoPath([string]$Path) {
    if ([IO.Path]::IsPathRooted($Path)) {
        return [IO.Path]::GetFullPath($Path)
    }
    return [IO.Path]::GetFullPath((Join-Path $repoRoot $Path))
}

function Resolve-Executable([string]$Candidate, [string]$Label) {
    if ($Candidate) {
        if (Test-Path -LiteralPath $Candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $Candidate).Path
        }
        $command = Get-Command $Candidate -ErrorAction SilentlyContinue
        if ($command) { return $command.Source }
    }
    throw "$Label was not found. Pass its explicit path."
}

function Invoke-Checked([string]$Label, [scriptblock]$Command) {
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE."
    }
}

$source = Resolve-RepoPath $SourceApk
$profileFile = Resolve-RepoPath $ProfilePath
if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
    throw "Source APK not found: $source"
}
if (-not (Test-Path -LiteralPath $profileFile -PathType Leaf)) {
    throw "Patch profile not found: $profileFile. Copy direct-server.example.json to a *.local.json file and set your LAN URL."
}

$profile = Get-Content -Raw -LiteralPath $profileFile | ConvertFrom-Json
if ($profile.schemaVersion -ne 1) { throw "Unsupported profile schemaVersion: $($profile.schemaVersion)" }
$baseUri = [Uri]$profile.serverBaseUrl
if ($baseUri.Scheme -ne 'http' -or -not $baseUri.Host -or $baseUri.AbsolutePath -ne '/' -or $baseUri.Query -or $baseUri.Fragment) {
    throw 'serverBaseUrl must have the form http://host:port with no path, query, or fragment.'
}

$actualSourceHashBefore = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
if ($actualSourceHashBefore -ne $profile.expectedSourceSha256) {
    throw "Source APK hash mismatch. Expected $($profile.expectedSourceSha256), found $actualSourceHashBefore."
}

if (-not $ApktoolJar) { $ApktoolJar = Join-Path $pipelineRoot '.tools\apktool_3.0.3.jar' }
$ApktoolJar = Resolve-RepoPath $ApktoolJar
if (-not (Test-Path -LiteralPath $ApktoolJar -PathType Leaf)) {
    throw "Apktool not found: $ApktoolJar. Run apk_patch_pipeline\install_apktool.ps1 or pass -ApktoolJar."
}

if (-not $AndroidSdkRoot) {
    $sdkCandidates = @(
        $env:ANDROID_SDK_ROOT,
        $env:ANDROID_HOME,
        (Join-Path $env:LOCALAPPDATA 'Android\Sdk')
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Container) }
    $AndroidSdkRoot = $sdkCandidates | Select-Object -First 1
}
if (-not $AndroidSdkRoot) { throw 'Android SDK root not found. Pass -AndroidSdkRoot.' }
$AndroidSdkRoot = [IO.Path]::GetFullPath($AndroidSdkRoot)

if (-not $BuildToolsVersion) {
    $BuildToolsVersion = if ($profile.buildToolsVersion) { [string]$profile.buildToolsVersion } else { '35.0.0' }
}
$buildTools = Join-Path $AndroidSdkRoot "build-tools\$BuildToolsVersion"
$zipalign = Join-Path $buildTools 'zipalign.exe'
$apksigner = Join-Path $buildTools 'apksigner.bat'
foreach ($tool in $zipalign, $apksigner) {
    if (-not (Test-Path -LiteralPath $tool -PathType Leaf)) { throw "Required Android build tool not found: $tool" }
}

$java = Resolve-Executable $(if ($JavaPath) { $JavaPath } else { 'java' }) 'Java'
$python = Resolve-Executable $(if ($PythonPath) { $PythonPath } else { 'python' }) 'Python'
$patcher = Join-Path $pipelineRoot 'patch_il2cpp_endpoints.py'
if (-not (Test-Path -LiteralPath $patcher -PathType Leaf)) { throw "Patcher not found: $patcher" }

$signingMode = if ($profile.signingMode) { [string]$profile.signingMode } else { 'development' }
if ($signingMode -notin @('development', 'custom')) { throw "Unsupported signingMode: $signingMode" }
if (-not $KeystorePath) {
    $KeystorePath = if ($signingMode -eq 'development') {
        Join-Path $pipelineRoot '.tools\signing\kickflight-local-test.jks'
    } else {
        throw 'Custom signing requires -KeystorePath.'
    }
}
$keystore = Resolve-RepoPath $KeystorePath

$keytool = Join-Path (Split-Path -Parent $java) 'keytool.exe'
if ($signingMode -eq 'development' -and -not (Test-Path -LiteralPath $keytool -PathType Leaf)) {
    $installedJavaKeytools = @()
    if ($env:ProgramFiles) {
        $javaInstallRoot = Join-Path $env:ProgramFiles 'Java'
        if (Test-Path -LiteralPath $javaInstallRoot -PathType Container) {
            $installedJavaKeytools = @(Get-ChildItem -LiteralPath $javaInstallRoot -Directory |
                Sort-Object Name -Descending |
                ForEach-Object { Join-Path $_.FullName 'bin\keytool.exe' })
        }
    }
    $keytoolCandidates = @(
        $(if ($env:JAVA_HOME) { Join-Path $env:JAVA_HOME 'bin\keytool.exe' }),
        $installedJavaKeytools
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) }
    $keytool = $keytoolCandidates | Select-Object -First 1
    if (-not $keytool) { $keytool = Resolve-Executable 'keytool' 'keytool' }
}
if ($signingMode -eq 'custom') {
    if (-not (Test-Path -LiteralPath $keystore -PathType Leaf)) { throw "Custom keystore not found: $keystore" }
    if (-not $env:APK_PATCH_STORE_PASSWORD) { throw 'Set APK_PATCH_STORE_PASSWORD for custom signing.' }
    if (-not $env:APK_PATCH_KEY_PASSWORD) { throw 'Set APK_PATCH_KEY_PASSWORD for custom signing.' }
}

$artifactDirectory = Join-Path $pipelineRoot 'artifacts'
New-Item -ItemType Directory -Force -Path $artifactDirectory | Out-Null
if (-not $OutputPath) {
    $safeHost = $baseUri.Authority.Replace(':', '-').Replace('[', '').Replace(']', '')
    $OutputPath = Join-Path $artifactDirectory "KickFlight-2.11.0-direct-$safeHost.apk"
} else {
    $OutputPath = Resolve-RepoPath $OutputPath
}
$output = [IO.Path]::GetFullPath($OutputPath)
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $output) | Out-Null

$workRoot = Join-Path $pipelineRoot '.work'
New-Item -ItemType Directory -Force -Path $workRoot | Out-Null
$work = Join-Path $workRoot ([Guid]::NewGuid().ToString('n'))
New-Item -ItemType Directory -Path $work | Out-Null
$decoded = Join-Path $work 'decoded'
$unsigned = Join-Path $work 'unsigned.apk'
$aligned = Join-Path $work 'aligned.apk'
$patchReportPath = Join-Path $work 'patch-report.json'
$verificationOutput = @()
$patchReport = $null

try {
    Invoke-Checked 'Apktool decode' { & $java -jar $ApktoolJar d -f -s $source -o $decoded }

    Invoke-Checked 'IL2CPP endpoint patch' {
        & $python $patcher `
            --metadata (Join-Path $decoded 'assets\bin\Data\Managed\Metadata\global-metadata.dat') `
            --arm64 (Join-Path $decoded 'lib\arm64-v8a\libil2cpp.so') `
            --armv7 (Join-Path $decoded 'lib\armeabi-v7a\libil2cpp.so') `
            --base-url $profile.serverBaseUrl `
            --report $patchReportPath
    }
    $patchReport = Get-Content -Raw -LiteralPath $patchReportPath | ConvertFrom-Json

    Invoke-Checked 'Apktool build' { & $java -jar $ApktoolJar b $decoded -o $unsigned }

    if ($signingMode -eq 'development' -and -not (Test-Path -LiteralPath $keystore -PathType Leaf)) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $keystore) | Out-Null
        Invoke-Checked 'Development signing-key generation' {
            & $keytool -genkeypair -keystore $keystore -storepass android -keypass android `
                -alias $KeyAlias -keyalg RSA -keysize 2048 -validity 10000 `
                -dname 'CN=KickFlight Local Test,OU=Development,O=Local,C=MX'
        }
    }

    Invoke-Checked 'zipalign' { & $zipalign -p -f 4 $unsigned $aligned }

    $storePass = if ($signingMode -eq 'development') { 'pass:android' } else { 'env:APK_PATCH_STORE_PASSWORD' }
    $keyPass = if ($signingMode -eq 'development') { 'pass:android' } else { 'env:APK_PATCH_KEY_PASSWORD' }
    Invoke-Checked 'APK signing' {
        & $apksigner sign --ks $keystore --ks-key-alias $KeyAlias `
            --ks-pass $storePass --key-pass $keyPass `
            --v1-signing-enabled true --v2-signing-enabled true `
            --out $output $aligned
    }

    # Windows PowerShell 5 promotes native stderr to NativeCommandError when
    # ErrorActionPreference is Stop. Java 25 emits a harmless native-access
    # warning there, so capture it while trusting apksigner's actual exit code.
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $verificationOutput = @(& $apksigner verify --verbose --print-certs $output 2>&1)
        $verificationExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    $verificationOutput = @($verificationOutput | ForEach-Object {
        if ($_ -is [System.Management.Automation.ErrorRecord]) {
            if ($_.Exception.Message) { [string]$_.Exception.Message }
        } else {
            [string]$_
        }
    } | Where-Object { $_ })
    if ($verificationExitCode -ne 0) { throw "APK signature verification failed with exit code $verificationExitCode." }
    $verificationOutput | ForEach-Object { Write-Host $_ }
    Invoke-Checked 'APK alignment verification' { & $zipalign -c -p 4 $output }
} finally {
    if (-not $KeepWorkDirectory -and (Test-Path -LiteralPath $work)) {
        $resolvedWork = [IO.Path]::GetFullPath($work)
        $resolvedRoot = [IO.Path]::GetFullPath($workRoot) + [IO.Path]::DirectorySeparatorChar
        if (-not $resolvedWork.StartsWith($resolvedRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove unexpected work directory: $resolvedWork"
        }
        Remove-Item -LiteralPath $resolvedWork -Recurse -Force
    }
}

$actualSourceHashAfter = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
if ($actualSourceHashAfter -ne $actualSourceHashBefore) {
    throw "Immutable source APK changed during the build: before=$actualSourceHashBefore after=$actualSourceHashAfter"
}
$outputHash = (Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash
$report = [ordered]@{
    schemaVersion = 1
    generatedAtUtc = [DateTimeOffset]::UtcNow.ToString('o')
    profileName = $profile.profileName
    profileSha256 = (Get-FileHash -LiteralPath $profileFile -Algorithm SHA256).Hash
    source = [ordered]@{ fileName = [IO.Path]::GetFileName($source); sha256 = $actualSourceHashBefore }
    target = [ordered]@{ serverBaseUrl = [string]$profile.serverBaseUrl; packageVersion = '2.11.0' }
    tools = [ordered]@{
        apktoolSha256 = (Get-FileHash -LiteralPath $ApktoolJar -Algorithm SHA256).Hash
        buildToolsVersion = $BuildToolsVersion
        python = $python
        java = $java
    }
    signing = [ordered]@{ mode = $signingMode; keyAlias = $KeyAlias; keystoreSha256 = (Get-FileHash -LiteralPath $keystore -Algorithm SHA256).Hash }
    output = [ordered]@{ fileName = [IO.Path]::GetFileName($output); sha256 = $outputHash; bytes = (Get-Item -LiteralPath $output).Length }
    verification = @($verificationOutput | ForEach-Object { [string]$_ })
    patch = $patchReport
}
$buildReportPath = "$output.build-report.json"
$report | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $buildReportPath -Encoding utf8

Write-Host "Patched APK: $output"
Write-Host "SHA-256:    $outputHash"
Write-Host "Server URL: $($profile.serverBaseUrl)"
Write-Host "Report:     $buildReportPath"
