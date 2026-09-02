# Prompt de continuación — APKs de Kick-Flight para el servidor comunitario

## Misión

Trabaja en el repositorio de preservación y tooling:

`C:\Users\Gixar\Documentos\Variedad\Kick-Flight-Assets`

Este repositorio es dueño del APK base local, el análisis estático, el pipeline de assets y el generador reproducible de APKs parcheadas. El servidor vive en un repositorio separado:

`C:\Users\Gixar\Documentos\Variedad\Kick-Flight-Private-Server`

No mezcles responsabilidades. En el repositorio de assets puedes mantener análisis y tooling de transformación. En el repositorio del servidor deben vivir API, fixtures, codecs, pruebas, capturas redacted y operación. Nunca copies al servidor el APK, bundles, dumps completos, claves o assets protegidos.

Tu objetivo al usar este prompt es continuar el pipeline de APK de manera segura, reproducible y versionada para que miembros autorizados de la comunidad puedan conectar su copia de Kick-Flight al servidor privado. No contactes ni hagas proxy a la infraestructura histórica de Grenge.

## Estado verificado

- APK: `base.apk` (ignorada por Git e inmutable).
- SHA-256: `F79F1B48F86C4F5973C763CBC6C166BD6C42CC83D4E36ECA75D7D1CAB74AD8D1`.
- Paquete: `jp.grenge.kickflight`.
- Versión: `2.11.0`, `versionCode 55`.
- Unity: `2018.4.11f1`.
- Scripting: IL2CPP; metadata 24.1 (cabecera 24).
- ABIs: `arm64-v8a` y `armeabi-v7a`.
- API principal: `kickflight-api.grenge.jp`.
- Catálogo Octo: `colorful-api-octo-sb.grenge.jp`.
- Recursos: `kickflight-resource-api.grenge.jp`.
- Matchmaking posterior: frontend gRPC de OpenMatch.
- Tiempo real posterior: Photon PUN/LoadBalancing.

La Fase 1 del servidor ya fue completada: una APK parcheada mediante conexión HTTP directa alcanzó la pantalla de título/TAP START. No vuelvas a crear el servidor ni declares esta comprobación basándote solamente en tests; lee primero el resultado actual en el repo del servidor.

Secuencia first-party observada para llegar al título:

1. `POST /boot/index` a la API principal: HTTP 200, `x-app-status-code: 0`, cuerpo binario D2C de 96 bytes.
2. `GET /v1/list/12345/0` al servicio de recursos: HTTP 200, Database protobuf de Octo con revisión 1 y listas vacías.

El cuerpo de boot usa AES-256-CBC con PKCS#7 y un IV de 16 bytes antepuesto. Trata este dato como un contrato técnico del protocolo local, no como autorización para reutilizar secretos históricos. El servidor debe generar únicamente identidades y datos comunitarios nuevos.

## Implementación actual del generador

Lee completamente `AGENTS.md` y `apk_patch_pipeline/README.md` antes de editar. Las piezas principales son:

- `apk_patch_pipeline/build_patched_apk.ps1`: orquestación decode → patch → rebuild → align → sign → verify;
- `apk_patch_pipeline/patch_il2cpp_endpoints.py`: transformación version-locked y transaccional de metadata y librerías;
- `apk_patch_pipeline/profiles/direct-server.example.json`: perfil sin secretos;
- `apk_patch_pipeline/install_apktool.ps1`: descarga verificada de Apktool 3.0.3;
- `apk_patch_pipeline/test_patch_il2cpp_endpoints.py`: pruebas unitarias sintéticas.

El perfil exige `serverBaseUrl` con forma `http://host:port`, sin ruta/query/fragment. El HTTP directo evita depender de proxy o CA en Android. La política Android recuperada permite cleartext, pero el código nativo fuerza HTTPS en puntos específicos y por eso también se aplican dos parches de instrucción.

Invariantes exactos del parche:

- metadata sanity `0xFAB11BAF`, versión de cabecera `24`;
- `https://colorful-api-octo-sb.grenge.jp` → URL base local;
- `https://kickflight-resource-api.grenge.jp` → URL base local;
- `kickflight-api.grenge.jp/` → autoridad local más `/`;
- ARM64 offset `0x31B5024`, guard `28118a9a`, reemplazo `e8030aaa` (`mov x8,x10`);
- ARMv7 offset `0x2AC1798`, guard `02309f17`, reemplazo `0000a0e1` (`mov r0,r0`).

Apktool fijado: 3.0.3, SHA-256 `DBF930B076C6B9BE08D57C449CACEFC3BDD6B71EBD59B3066FC0E1F5B14F9423`. Build Tools verificados: 35.0.0.

## Evidencias disponibles

No repitas una decompilación completa sin una razón concreta. Usa:

- `server_revival_analysis/README.md`;
- `server_revival_analysis/PRIVATE_SERVER_REVIVAL_PLAN.md`;
- `server_revival_analysis/protocol_inventory.json`;
- los outputs grandes ignorados de JADX e Il2CppDumper, si están presentes localmente;
- `PIPELINE_OUTPUT_V3/report_v3.json` y manifests para investigación de assets;
- el repo del servidor para contratos y resultados de runtime actuales.

La configuración Android recuperada permite cleartext, confía en certificados del sistema/usuario y nombra los dominios first-party, localhost y la dirección histórica `192.168.0.96`. No se encontró pinning en la capa Java. Esto no elimina la validación nativa que motivó los parches anteriores.

Headers conocidos incluyen `x-app-access-token`, `x-app-adid`, `x-app-adjust-adid`, `x-app-application-version`, `x-app-asset-platform`, `x-app-asset-revision`, `x-app-asset-version`, `x-app-country-code`, `x-app-datetime`, `x-app-device-name`, `x-app-language`, `x-app-master-hash`, `x-app-os-version`, `x-app-platform`, `x-app-response-cache-id`, `x-app-status-code`, `x-app-user-agent`, `x-app-user-id` y `X-OCTO-KEY`. Nunca registres valores sensibles completos.

## Reglas de trabajo

1. Inspecciona `git status` y preserva cambios ajenos.
2. Comprueba el hash de `base.apk` antes y después de cualquier build.
3. Modifica archivos con parches revisables; no edites el APK fuente.
4. Mantén validaciones fail-closed: un guard desconocido debe detener el build, no intentar un parche aproximado.
5. No agregues a Git APKs, claves, perfiles locales, herramientas descargadas, áreas de trabajo o artefactos generados.
6. Todo soporte a otra versión del cliente requiere un perfil/versionado propio, hashes, offsets verificados, fixtures de prueba y documentación; no relajes los guards existentes.
7. No automatices acciones destructivas sobre un dispositivo. Instalar/desinstalar, borrar datos o cambiar proxy/DNS requiere alcance explícito y procedimientos reversibles.
8. No uses servicios históricos para descubrir respuestas. Obtén contratos de análisis local y observación contra el servidor comunitario.

## Validación obligatoria

Ejecuta como mínimo:

```powershell
python -m unittest discover -s .\apk_patch_pipeline -p 'test_*.py' -v
git diff --check
```

Cuando cambie el generador, realiza además un build completo con un perfil local y verifica:

- hash del APK fuente intacto;
- los tres literales y ambos guards aplicados una sola vez;
- reconstrucción de Apktool exitosa;
- `zipalign -c` exitoso;
- `apksigner verify --verbose --print-certs` exitoso;
- `*.build-report.json` con `patch` no nulo, hashes y detalles de las cinco sustituciones;
- los artefactos permanecen ignorados por Git.

Si hay un Android autorizado disponible, una prueba de runtime debe confirmar que todas las llamadas first-party van al host local y que la app alcanza al menos el hito previamente logrado. Reporta por separado tests estáticos, build firmado y evidencia de dispositivo; ninguno sustituye a los demás.

## Próximo límite funcional

El siguiente trabajo funcional comienza después de TAP START y probablemente entra en auth/onboarding. No implementes cientos de rutas por anticipado. Captura el siguiente request local, identifica su DTO/codec, crea el contrato mínimo en el repo del servidor, añade una prueba y repite. OpenMatch, Photon, batalla completa, tienda, gacha y progresión completa siguen fuera de alcance hasta que un flujo concreto los requiera.

## Entrega esperada

Al terminar una iteración, deja código y documentación coherentes, pruebas verdes, hashes de evidencia y `git status` sin artefactos generados. Explica qué cambió, qué validaste realmente, cuál es el siguiente bloqueo observado y cualquier riesgo de distribución o firma. No declares compatibilidad con una APK o arquitectura que no hayas validado.
