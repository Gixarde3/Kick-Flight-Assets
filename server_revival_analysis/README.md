# Kick-Flight server-revival analysis

This directory contains the reproducible static-analysis outputs used to build the private-server plan. It does not contain a server implementation and it does not contact the retired production services.

## Confirmed client facts

- Package: `jp.grenge.kickflight`
- APK version: `2.11.0` (`versionCode 55`)
- Unity: `2018.4.11f1`
- Backend: IL2CPP, metadata `24.1`
- ABIs: ARM64 and ARMv7
- Control API domain compiled into the client: `kickflight-api.grenge.jp`
- Octo/catalog host: `colorful-api-octo-sb.grenge.jp`
- Resource host: `kickflight-resource-api.grenge.jp`
- Matchmaking: OpenMatch gRPC frontend
- Realtime sessions: Photon PUN / Photon LoadBalancing

The decoded Android network-security policy permits cleartext and trusts both system and user-installed certificates. It names the production hosts, `localhost`, and the historical LAN development address `192.168.0.96`.

## Outputs

- `apk_extracted/`: the APK ZIP payload.
- `jadx/`: Java sources recovered from the two DEX files. JADX reported 13 non-fatal decompilation errors out of 4,454 classes.
- `jadx_resources/`: decoded manifest and Android resources.
- `il2cpp/`: IL2CPP type dump, native mappings, strings, and 104 reconstructed dummy assemblies.
- `protocol_inventory.json`: generated hosts, route candidates, headers, and model inventory.
- `PRIVATE_SERVER_REVIVAL_PLAN.md`: implementation roadmap and acceptance gates.
- `tools/`: pinned analysis tools and their downloaded archives.

## Reproduce the inventory

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\server_revival_analysis\build_inventory.ps1
```

The APK extraction and decompilation commands used were:

```powershell
New-Item -ItemType Directory -Force .\server_revival_analysis\apk_extracted
tar -xf .\base.apk -C .\server_revival_analysis\apk_extracted

.\server_revival_analysis\tools\il2cppdumper\Il2CppDumper.exe `
  .\server_revival_analysis\apk_extracted\lib\arm64-v8a\libil2cpp.so `
  .\server_revival_analysis\apk_extracted\assets\bin\Data\Managed\Metadata\global-metadata.dat `
  .\server_revival_analysis\il2cpp

$env:JADX_CONFIG_DIR = (Resolve-Path .\server_revival_analysis\jadx_config).Path
$env:JADX_CACHE_DIR = (Resolve-Path .\server_revival_analysis\jadx_cache).Path
$env:JADX_TMP_DIR = (Resolve-Path .\server_revival_analysis\jadx_tmp).Path
.\server_revival_analysis\tools\jadx\bin\jadx.bat `
  -d .\server_revival_analysis\jadx --show-bad-code --no-res --config none .\base.apk
```

Tool versions used:

- JADX `1.5.6`; archive SHA-256 `545EA2BE9C242511BC145755CF4BDA2485ADE42966E096F8B4D3DA2A230E8974`
- Il2CppDumper `6.7.46`; archive SHA-256 `DB9BBBC538E33ABFB057C7757AE5D6C1F16A05FDC0D13AF8A5A67EA31FAABA0C`
- Base APK SHA-256 `F79F1B48F86C4F5973C763CBC6C166BD6C42CC83D4E36ECA75D7D1CAB74AD8D1`

Il2CppDumper prints a console-input exception after successful generation when run with redirected input. The `Done!`, structure generation, dummy DLL generation, and resulting files confirm the analysis completed before that exit-path exception.
