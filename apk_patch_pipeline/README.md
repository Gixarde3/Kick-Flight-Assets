# Pipeline reproducible de APK parcheada

Este directorio genera una APK de desarrollo de Kick-Flight 2.11.0 que apunta directamente a una instancia autorizada del servidor comunitario. El APK de entrada nunca se modifica. La salida, el área de trabajo, las herramientas descargadas y las claves de firma están ignoradas por Git.

El parche está bloqueado deliberadamente a la APK conocida. Antes de escribir sobre la copia de trabajo valida el SHA-256 del APK, la cabecera de metadata IL2CPP, los tres literales de red y las instrucciones esperadas de ARM64 y ARMv7. Si cambia cualquiera de esos invariantes, el proceso se detiene.

## Requisitos

- Windows PowerShell 5.1 o PowerShell 7;
- Python 3.10 o superior;
- Java y `keytool` disponibles;
- Android SDK Build Tools 35.0.0 (`zipalign.exe` y `apksigner.bat`);
- `base.apk` legalmente obtenido en la raíz del repositorio, con SHA-256 `F79F1B48F86C4F5973C763CBC6C166BD6C42CC83D4E36ECA75D7D1CAB74AD8D1`.

Instala la versión fijada de Apktool:

```powershell
.\apk_patch_pipeline\install_apktool.ps1
```

El instalador verifica el SHA-256 del JAR y lo guarda bajo `.tools/`, que no se publica.

## Configuración y compilación

Crea un perfil local a partir del ejemplo:

```powershell
Copy-Item .\apk_patch_pipeline\profiles\direct-server.example.json `
  .\apk_patch_pipeline\profiles\direct-server.local.json
```

Edita únicamente `serverBaseUrl` con una dirección HTTP alcanzable desde Android, por ejemplo `http://192.168.1.25:18080`. No uses `localhost` desde un dispositivo físico. El perfil local está ignorado porque normalmente contiene datos propios de la red.

Genera la APK:

```powershell
.\apk_patch_pipeline\build_patched_apk.ps1
```

Si el SDK no puede descubrirse automáticamente:

```powershell
.\apk_patch_pipeline\build_patched_apk.ps1 `
  -AndroidSdkRoot 'C:\Android\Sdk' `
  -BuildToolsVersion '35.0.0'
```

La salida predeterminada queda en `apk_patch_pipeline/artifacts/` junto a un `*.build-report.json`. El reporte contiene hashes de entrada/salida, perfil, herramientas, firma, verificación y cada cambio realizado. La primera ejecución crea una clave de desarrollo local con contraseña conocida `android`; sirve solamente para instalaciones comunitarias de prueba y nunca debe distribuirse como identidad de producción.

Para firmar con una clave administrada externamente, cambia el perfil a `"signingMode": "custom"`, pasa `-KeystorePath` y `-KeyAlias`, y define `APK_PATCH_STORE_PASSWORD` y `APK_PATCH_KEY_PASSWORD` en el entorno. No agregues la clave ni las contraseñas al repositorio.

## Qué cambia

En `global-metadata.dat` se redirigen los literales:

- `https://colorful-api-octo-sb.grenge.jp` → URL base local;
- `https://kickflight-resource-api.grenge.jp` → URL base local;
- `kickflight-api.grenge.jp/` → autoridad local más `/`.

En `libil2cpp.so` se conserva HTTP en las dos arquitecturas:

- ARM64, offset `0x31B5024`: `28118a9a` → `e8030aaa`;
- ARMv7, offset `0x2AC1798`: `02309f17` → `0000a0e1`.

No se parchean respuestas, autenticación ni lógica de juego. El servidor privado es responsable de los contratos y nunca debe reenviar tráfico a los servicios históricos.

## Pruebas

```powershell
python -m unittest discover -s .\apk_patch_pipeline -p 'test_*.py' -v
```

Una validación completa requiere ejecutar el generador y comprobar que `apksigner verify` y `zipalign -c` aparecen en el reporte. Después puede instalarse manualmente con `adb install -r RUTA_APK`; desinstalar una versión firmada con otra clave puede borrar los datos locales de la app, por lo que esa acción no está automatizada.

## Límites de publicación

Se publica código, perfiles de ejemplo y documentación. No se publican APKs de entrada o salida, assets extraídos, claves, certificados, credenciales, capturas sensibles ni respuestas obtenidas de infraestructura histórica. Usa el pipeline únicamente con copias y servidores que tengas derecho a operar.
