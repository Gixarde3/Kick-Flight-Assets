param(
    [string]$ApkPath = "..\base.apk",
    [string]$DumpPath = ".\il2cpp\dump.cs",
    [string]$StringLiteralPath = ".\il2cpp\stringliteral.json",
    [string]$OutputPath = ".\protocol_inventory.json"
)

$ErrorActionPreference = "Stop"

$scriptRoot = $PSScriptRoot
$resolvedApk = (Resolve-Path (Join-Path $scriptRoot $ApkPath)).Path
$resolvedDump = (Resolve-Path (Join-Path $scriptRoot $DumpPath)).Path
$resolvedStrings = (Resolve-Path (Join-Path $scriptRoot $StringLiteralPath)).Path
$resolvedOutput = [IO.Path]::GetFullPath((Join-Path $scriptRoot $OutputPath))

$literalRecords = Get-Content -Raw -LiteralPath $resolvedStrings | ConvertFrom-Json
$literals = @($literalRecords.value | Where-Object { $_ -is [string] })
$dump = Get-Content -Raw -LiteralPath $resolvedDump

$hostSet = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach ($literal in $literals) {
    foreach ($match in [regex]::Matches($literal, '(?i)(?:https?|wss?)://([^/:\s{}]+)')) {
        [void]$hostSet.Add($match.Groups[1].Value)
    }
}

$routeCandidates = @(
    $literals |
        Where-Object {
            $_ -match '^[a-z][A-Za-z0-9]*/[A-Za-z0-9][A-Za-z0-9_./-]*$' -and
            $_ -notmatch '\.(unity3d|asset|png|jpg|json|xml|dll)$'
        } |
        Sort-Object -Unique
)

$headers = @(
    $literals |
        Where-Object { $_ -match '^(?i:x-app-[a-z0-9-]+|X-OCTO-KEY|X-ApiKey|Authorization|Content-Type|Content-type)$' } |
        Sort-Object -Unique
)

$contentTypes = @(
    $literals |
        Where-Object { $_ -match '^application/[A-Za-z0-9.+_-]+' } |
        Sort-Object -Unique
)

$typeMatches = [regex]::Matches(
    $dump,
    '(?m)^// Namespace: Colorful\.Networking\r?\n(?:(?:\[[^\r\n]+\])\r?\n)*public (?:(?:abstract|sealed) )?class ([A-Za-z0-9_]+)'
)
$networkTypes = @($typeMatches | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique)

$requestTypes = @($networkTypes | Where-Object { $_ -match 'Request(?:Data)?$' })
$responseTypes = @($networkTypes | Where-Object { $_ -match 'Response(?:Data)?$' })
$dataTypes = @($networkTypes | Where-Object { $_ -match 'Data$' -and $_ -notmatch '(?:Request|Response)Data$' })

$inventory = [ordered]@{
    generated_at_utc = [DateTime]::UtcNow.ToString('o')
    apk = [ordered]@{
        path = 'base.apk'
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $resolvedApk).Hash
        package = 'jp.grenge.kickflight'
        version_name = '2.11.0'
        version_code = 55
        unity_version = '2018.4.11f1'
        scripting_backend = 'IL2CPP'
        il2cpp_metadata_version = '24.1'
        architectures = @('arm64-v8a', 'armeabi-v7a')
    }
    recovered_network = [ordered]@{
        primary_api_domain = 'kickflight-api.grenge.jp'
        octo_api_host = 'colorful-api-octo-sb.grenge.jp'
        resource_host = 'kickflight-resource-api.grenge.jp'
        hosts = @($hostSet | Sort-Object)
        request_headers = $headers
        content_types = $contentTypes
        route_candidate_count = $routeCandidates.Count
        route_candidates = $routeCandidates
    }
    recovered_models = [ordered]@{
        colorful_networking_type_count = $networkTypes.Count
        request_type_count = $requestTypes.Count
        response_type_count = $responseTypes.Count
        data_type_count = $dataTypes.Count
        request_types = $requestTypes
        response_types = $responseTypes
        data_types = $dataTypes
    }
    services = [ordered]@{
        control_plane = 'UnityWebRequest DTO API (JSON indicators present)'
        asset_catalog = 'Octo protobuf catalog plus UnityFS/CRI payload delivery'
        matchmaking = 'OpenMatch gRPC Frontend: CreateTicket, DeleteTicket, GetTicket, GetAssignments'
        realtime = 'Photon PUN / LoadBalancing rooms, properties, events, and RPCs'
    }
}

$parent = Split-Path -Parent $resolvedOutput
if ($parent) {
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
}
$inventory | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $resolvedOutput -Encoding UTF8

[PSCustomObject]@{
    Output = $resolvedOutput
    Routes = $routeCandidates.Count
    NetworkTypes = $networkTypes.Count
    Requests = $requestTypes.Count
    Responses = $responseTypes.Count
    DataTypes = $dataTypes.Count
}
