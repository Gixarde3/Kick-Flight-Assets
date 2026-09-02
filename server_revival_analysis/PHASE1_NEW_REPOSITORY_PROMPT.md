# Prompt de implementación — Nuevo repositorio Kick-Flight Private Server, Fase 1

> Estado histórico: este prompt ya fue ejecutado y la Fase 1 alcanzó la pantalla de título/TAP START. Para continuar el tooling de APK usa `../APK_PATCH_PIPELINE_CONTINUATION_PROMPT.md`; para continuar el backend consulta el estado actual del repositorio `Kick-Flight-Private-Server`.

## Instrucción principal

Trabaja como agente principal de implementación y crea un **repositorio Git nuevo e independiente**, dedicado exclusivamente al servidor privado de Kick-Flight.

El repositorio actual contiene la APK, assets y evidencias de ingeniería inversa. Debe tratarse únicamente como una fuente externa de lectura:

`C:\Users\Gixar\Documentos\Variedad\Kick-Flight-Assets`

Usa esta ruta como repositorio nuevo del servidor:

`C:\Users\Gixar\Documentos\Variedad\Kick-Flight-Private-Server`

En este documento:

- `SOURCE_REPO` significa `C:\Users\Gixar\Documentos\Variedad\Kick-Flight-Assets`.
- `SERVER_REPO` significa `C:\Users\Gixar\Documentos\Variedad\Kick-Flight-Private-Server`.

Tu misión es crear `SERVER_REPO`, inicializarlo con `git init` y **crear y completar allí la Fase 1**. No configures un remote, no publiques el repositorio y no hagas push. Si la ruta ya existe, inspecciónala y preserva cualquier contenido previo; no la sobrescribas ni la reinicialices destructivamente.

Todo el código del servidor, solución .NET, tests, scripts, fixtures, documentación y configuración debe vivir en `SERVER_REPO`. No escribas implementación dentro de `SOURCE_REPO`. La única excepción es leer este prompt y los artefactos de análisis ya existentes.

No te limites a proponer otra planificación ni a generar scaffolding vacío. Inspecciona las evidencias existentes, implementa el harness local, ejecútalo, crea pruebas, conecta un cliente Android si el entorno lo permite y avanza iterativamente hasta eliminar el `Network Error` inicial o identificar con evidencia reproducible el último contrato concreto que aún lo provoca.

El resultado buscado es que la APK original deje de fallar inmediatamente con `Network Error`, alcance el flujo de título/inicio y que todas las conexiones first-party de Kick-Flight estén redirigidas, registradas y controladas localmente.

## Contexto ya confirmado

No repitas desde cero la extracción general de la APK. Ya se hizo y estos hechos están verificados localmente:

- APK: `base.apk`
- SHA-256: `F79F1B48F86C4F5973C763CBC6C166BD6C42CC83D4E36ECA75D7D1CAB74AD8D1`
- Paquete Android: `jp.grenge.kickflight`
- Versión: `2.11.0`, `versionCode 55`
- Unity: `2018.4.11f1`
- Backend de scripts: IL2CPP
- Metadata IL2CPP: `24.1`
- Arquitecturas: `arm64-v8a` y `armeabi-v7a`
- Dominio principal compilado en `NetworkManager`: `kickflight-api.grenge.jp`
- Host del catálogo Octo: `colorful-api-octo-sb.grenge.jp`
- Host de recursos: `kickflight-resource-api.grenge.jp`
- El cliente utiliza UnityWebRequest y DTOs `Colorful.Networking` para la API de control.
- Hay indicadores de cuerpos JSON para la API de control.
- Octo usa un catálogo protobuf, `X-OCTO-KEY` y payloads UnityFS/CRI.
- El matchmaking posterior usa el frontend gRPC `openmatch.Frontend`.
- El realtime posterior usa Photon PUN/LoadBalancing.
- OpenMatch y Photon están fuera del alcance de esta fase salvo que el cliente intente inicializarlos prematuramente; en ese caso se debe bloquear o simular solo el mínimo necesario para llegar al título.

La configuración Android recuperada es favorable para pruebas locales:

- `android:usesCleartextTraffic="true"`
- `cleartextTrafficPermitted="true"`
- confía en certificados del sistema y certificados instalados por el usuario;
- incluye explícitamente `grenge.jp`, los tres hosts anteriores, `localhost` y `192.168.0.96`;
- no se encontró pinning de certificado en la capa Java de la aplicación.

El `NetworkManager` recuperado contiene:

- dominio `kickflight-api.grenge.jp`;
- selección HTTP/HTTPS;
- timeout de 30 segundos;
- tres reintentos;
- `InitializeAsync` en RVA `0x31B4774`;
- `LoadData` en RVA `0x31B4E84`;
- `SetEnvironment` en RVA `0x31B4F7C`.

No asumas que una respuesta HTTP 200 con `{}` es válida. Debes observar la secuencia real, asociar cada ruta con su DTO y construir el contrato mínimo que permita avanzar al cliente.

## Fuentes externas obligatorias, solo lectura

Lee estas fuentes desde `SOURCE_REPO` antes de crear código en `SERVER_REPO`:

1. `SOURCE_REPO/server_revival_analysis/PRIVATE_SERVER_REVIVAL_PLAN.md`
2. `SOURCE_REPO/server_revival_analysis/README.md`
3. `SOURCE_REPO/server_revival_analysis/protocol_inventory.json`
4. `SOURCE_REPO/server_revival_analysis/il2cpp/dump.cs`
5. `SOURCE_REPO/server_revival_analysis/il2cpp/stringliteral.json`
6. `SOURCE_REPO/server_revival_analysis/jadx_resources/resources/AndroidManifest.xml`
7. `SOURCE_REPO/server_revival_analysis/jadx_resources/resources/res/xml/network_security_config.xml`
8. `SOURCE_REPO/server_revival_analysis/jadx/sources/`
9. `SOURCE_REPO/PIPELINE_OUTPUT_V3/report_v3.json` y sus manifests cuando la secuencia llegue a Octo/assets.

Los directorios grandes de decompilación existen en `SOURCE_REPO` y deben usarse como evidencia sin copiarlos al nuevo repositorio. Copia únicamente esquemas, fixtures redacted o documentación derivada que sean imprescindibles para el servidor, indicando su procedencia. No copies la APK, bundles, dummy DLLs, dumps completos ni assets protegidos a `SERVER_REPO`.

Herramientas ya descargadas:

- JADX `1.5.6`: `SOURCE_REPO/server_revival_analysis/tools/jadx/`
- Il2CppDumper `6.7.46`: `SOURCE_REPO/server_revival_analysis/tools/il2cppdumper/`

Il2CppDumper ya generó `dump.cs`, `script.json`, `stringliteral.json`, `il2cpp.h` y 104 dummy DLLs. Las dummy DLLs contienen estructura y firmas, no los cuerpos C# originales.

## Headers first-party recuperados

El servidor/capturador debe registrar y comprender, sin exponer valores sensibles, al menos:

- `x-app-access-token`
- `x-app-adid`
- `x-app-adjust-adid`
- `x-app-application-version`
- `x-app-asset-platform`
- `x-app-asset-revision`
- `x-app-asset-version`
- `x-app-country-code`
- `x-app-datetime`
- `x-app-device-name`
- `x-app-language`
- `x-app-master-hash`
- `x-app-os-version`
- `x-app-platform`
- `x-app-response-cache-id`
- `x-app-status-code`
- `x-app-user-agent`
- `x-app-user-id`
- `X-OCTO-KEY`

Redacta siempre access tokens, IDs publicitarios, UUID de dispositivo, cookies y cualquier credencial. En archivos de captura conserva nombre del header, presencia, longitud y un hash corto cuando sea útil, pero no el secreto completo.

## Rutas probablemente relevantes

La secuencia exacta debe descubrirse dinámicamente. Entre los literales recuperados están:

- `auth/prepare`
- `auth/create`
- `auth/index`
- `agreement/read`
- `agreement/dataUsage`
- `download/master`
- rutas/modelos de boot, startup y home recuperados en `dump.cs`
- rutas de usuario necesarias para onboarding

No implementes masivamente las 539 rutas candidatas. Implementa únicamente las que el cliente alcance en orden durante esta fase.

## Alcance exacto de la Fase 1

### Incluido

1. Crear e inicializar `SERVER_REPO` como repositorio Git independiente, con README, política de preservación y `.gitignore` adecuados. No elijas una licencia pública sin una decisión explícita del usuario.
2. Auditar dependencias locales: .NET 8, Android SDK/ADB, emulador o dispositivo, OpenSSL/certificados, Docker si está disponible y herramientas de captura.
3. Crear un servidor HTTP/HTTPS local que distinga los tres hosts first-party mediante `Host`/SNI.
4. Crear logging estructurado y seguro de método, host, ruta, query, headers redacted, tamaño, SHA-256 y vista segura del body.
5. Crear un sistema de fixtures configurable por `host + método + ruta`, sin recompilar el servidor para cada experimento.
6. Prohibir por diseño el proxy hacia los servidores históricos. El harness no debe reenviar tráfico a producción.
7. Crear redirección reproducible para emulador/dispositivo: proxy local, DNS local o hosts, según las capacidades reales del entorno.
8. Crear una CA/certificados de desarrollo solo dentro de una carpeta ignorada por Git, con instrucciones claras para instalarlos y retirarlos.
9. Lanzar `SOURCE_REPO/base.apk`, capturar `adb logcat`, correlacionar `Network Error` con la petición/respuesta concreta y guardar una transcripción redacted dentro de `SERVER_REPO`.
10. Reconstruir e implementar la respuesta mínima válida de cada bloqueo alcanzado hasta que el cliente supere el error inicial y llegue al título/inicio.
11. Crear pruebas automatizadas para routing, redacción, fixtures, ausencia de upstream, contratos descubiertos y health checks.
12. Documentar todos los pasos para reproducir el resultado desde una máquina limpia que tenga acceso legal a su propia APK.

### Fuera de alcance

- Matchmaking completo de OpenMatch.
- Servidor Photon o batallas multiplayer.
- Progresión completa, tiendas, gacha, social y rankings.
- Restauración completa de Octo y todos los assets; solo el mínimo si bloquea el título.
- Contactar, probar o enviar peticiones a servidores históricos de Grenge.
- Usar credenciales, API keys o tokens históricos como autenticación del nuevo servicio.
- Publicar APKs, assets o secretos.

## Arquitectura requerida

Usa .NET 8 y ASP.NET Core, salvo que una evidencia técnica fuerte descubierta en `SOURCE_REPO` justifique otra cosa.

Estructura mínima sugerida para la raíz de `SERVER_REPO`:

```text
Kick-Flight-Private-Server/
  README.md
  PRESERVATION_POLICY.md
  .gitignore
  KickFlight.PrivateServer.sln
  src/
    KickFlight.BootstrapApi/
  tests/
    KickFlight.BootstrapApi.Tests/
  config/
    fixtures/
    first-party-hosts.json
  scripts/
    check-prerequisites.ps1
    run-local.ps1
    create-dev-cert.ps1
    configure-android-proxy.ps1
    restore-android-network.ps1
    launch-and-capture.ps1
  captures/
    .gitignore
  certs/
    .gitignore
  docs/
    ANDROID_SETUP.md
    DISCOVERED_STARTUP_FLOW.md
    PHASE1_RESULT.md
```

Los nombres pueden ajustarse, pero conserva separación entre servidor, pruebas, scripts, fixtures, capturas y certificados.

### Servidor bootstrap

Debe incluir:

- `/health/live` y `/health/ready`;
- escucha configurable, con HTTP para depuración y HTTPS para equivalencia de host;
- selección de fixture por host, método y ruta;
- recarga de fixtures sin recompilar, si es razonable;
- respuesta default explícita y configurable, preferiblemente un error local identificable, nunca un forward;
- correlation ID por petición;
- logs JSON legibles por máquina;
- almacenamiento opcional de bodies en `captures/`, con límites de tamaño;
- redacción determinista de secretos;
- salida que muestre claramente `request -> fixture -> response`;
- modo estricto que falle si se solicita una ruta sin fixture;
- encabezados de respuesta configurables, incluyendo `Content-Type` y `x-app-status-code` cuando el contrato lo requiera.

El servidor debe poder servir simultáneamente:

- `kickflight-api.grenge.jp`
- `colorful-api-octo-sb.grenge.jp`
- `kickflight-resource-api.grenge.jp`

### Captura y redirección Android

Primero detecta qué existe realmente: `adb devices`, emuladores instalados, permisos root, versión de Android e IP LAN.

Prioridad de técnicas:

1. Proxy explícito del emulador/dispositivo con CA de desarrollo instalada, si permite conservar los hosts originales y observar HTTPS.
2. DNS local controlado que resuelva solo los tres hosts first-party a la máquina del servidor.
3. Archivo hosts del emulador únicamente si es un emulador de pruebas con root/remount y el usuario autoriza esa modificación.
4. Patch reproducible de dominio/SSL solo como último recurso.

No cambies DNS/hosts globales de la máquina ni hagas root/remount de un dispositivo real sin explicar el cambio y obtener autorización. Todo script que modifique proxy o red debe tener su script inverso y mostrar el estado anterior.

El harness debe impedir que esos tres hosts salgan a Internet. Los SDKs third-party pueden bloquearse durante la investigación si generan ruido, pero documenta cada bloqueo.

### Investigación del contrato mínimo

Para cada petición que bloquee el avance:

1. Registra host, método, ruta, orden, headers presentes y body redacted.
2. Busca el literal de la ruta en `stringliteral.json` y `dump.cs`.
3. Identifica la clase `*Request`, su `*RequestData`, `*Response`, `*ResponseData` y campos públicos.
4. Busca el caller y el estado de cliente que consume la respuesta.
5. Determina JSON, protobuf u otro formato por contenido, DTO y `Content-Type`.
6. Construye el fixture mínimo conservando nombres/casing y valores default correctos.
7. Añade una prueba contractual antes de continuar.
8. Relanza desde un estado de app conocido y confirma si el bloqueo avanzó a la siguiente petición.

Si la respuesta parece correcta pero el cliente aún falla, inspecciona solo entonces el cuerpo nativo relevante mediante RVA/script mapping. No desensambles toda `libil2cpp.so` sin objetivo.

Busca especialmente:

- envelope común de respuesta;
- `x-app-status-code`;
- códigos de mantenimiento/versión;
- hash o token derivado;
- respuesta-cache;
- serialización y casing;
- compresión gzip;
- revisión/hash de master data;
- cualquier validación de hora del servidor.

No inventes semántica de producción innecesaria. Para esta fase usa IDs y tokens nuevos, deterministas o locales, claramente marcados como datos de comunidad.

## Estrategia de APK

Mantén `SOURCE_REPO/base.apk` inmutable. Verifica su hash antes y después. No copies la APK a `SERVER_REPO`.

Evita modificar la APK mientras proxy/DNS/CA funcionen. Si se demuestra que un patch es imprescindible:

1. explica la evidencia exacta;
2. crea un script reproducible bajo `scripts/`;
3. guarda diffs/manifests, nunca solo el binario resultante;
4. usa una clave de desarrollo nueva, nunca la firma histórica;
5. registra hashes de entrada y salida;
6. no agregues el APK generado a Git;
7. prueba instalación limpia y actualización por separado.

## Orden de trabajo obligatorio

1. Lee las instrucciones (`AGENTS.md` si existe) de `SOURCE_REPO` y de `SERVER_REPO`, además de las fuentes externas enumeradas.
2. Verifica que `SOURCE_REPO` se mantendrá solo lectura para este trabajo.
3. Inspecciona si `SERVER_REPO` ya existe. Si no existe, créalo e inicializa allí un repositorio con `git init`; si existe, preserva su estado y cambios.
4. Crea `.gitignore` antes de generar certificados, capturas, bases de datos, APKs o artefactos voluminosos.
5. Crea un plan de ejecución breve y mantenlo actualizado.
6. Audita herramientas/dispositivo sin modificar estado externo.
7. Implementa en `SERVER_REPO` el servidor, fixtures, logs y pruebas.
8. Levanta el servidor y valida health/routing con peticiones locales que usen los tres `Host` headers.
9. Configura captura/redirección Android de manera reversible.
10. Lanza la app desde `SOURCE_REPO/base.apk`, captura evidencia y localiza el primer bloqueo.
11. Implementa contratos uno por uno hasta superar `Network Error`.
12. Ejecuta todas las pruebas y una reproducción limpia.
13. Completa la documentación en `SERVER_REPO` y reporta evidencia, limitaciones y siguiente petición pendiente.

No pares después de crear la solución. Continúa mientras haya una acción segura y relevante que acerque al criterio de aceptación.

## Criterios de aceptación

La Fase 1 solo puede marcarse completa si se demuestra todo lo siguiente:

1. `dotnet test` pasa.
2. El servidor arranca con un solo comando documentado.
3. Los tres hosts first-party llegan al servidor local o están bloqueados explícitamente hasta que se necesiten.
4. Ninguna petición de esos hosts se reenvía a Internet.
5. Logs y capturas están redacted y no contienen tokens/IDs completos.
6. El cliente ya no muestra el `Network Error` inicial y alcanza el flujo de título/inicio, o una pantalla posterior inequívoca.
7. Existe evidencia: log del servidor, fragmento redacted de logcat, secuencia ordenada de requests y captura/pantalla si es posible.
8. La reproducción funciona después de detener/restaurar la configuración de red y volver a aplicarla con los scripts.
9. `base.apk` conserva exactamente su SHA-256 original.
10. `docs/PHASE1_RESULT.md` describe qué respuestas mínimas fueron necesarias, qué sigue sin implementar y cómo deshacer cambios en Android/red.

Si no hay emulador/dispositivo disponible, no declares la fase completa. En ese caso deja el harness, pruebas, scripts y fixtures listos; documenta el único bloqueo externo verificable y el comando exacto que debe ejecutar el usuario para continuar.

## Pruebas mínimas obligatorias

- Health endpoints.
- Routing diferenciado por host/método/ruta.
- Ruta desconocida en modo estricto.
- Recarga o lectura correcta de fixtures.
- Headers/body/binario y `Content-Type` configurables.
- Redacción de cada header sensible conocido.
- Límite de tamaño de captura.
- No-upstream: ninguna ruta puede crear una conexión saliente.
- Contrato de cada fixture real descubierto.
- Script de restauración de proxy/red validado de forma no destructiva.
- Hash de `base.apk` comprobado por script.

## Reglas de seguridad y preservación

- Trabaja solo con los archivos locales suministrados.
- No consultes ni ataques servicios retirados.
- No intentes obtener credenciales históricas.
- No expongas la API de captura fuera de LAN/localhost sin autenticación.
- No registres secretos completos.
- No borres outputs de preservación ni cambios ajenos.
- No uses comandos destructivos de Git.
- No agregues `SOURCE_REPO` como submódulo, subtree ni contenido vendorizado.
- No configures un remote ni publiques `SERVER_REPO` durante esta fase.
- No conviertas rutas admin/debug recuperadas en endpoints públicos.
- Todos los cambios de Android, proxy, CA y red deben ser reversibles y documentados.

## Entrega final esperada

En tu respuesta final, empieza por el resultado observable, no por una lista de actividades. Incluye:

- hasta qué pantalla llegó la app;
- qué request causaba originalmente `Network Error`;
- qué fixtures/contratos se implementaron;
- comandos para iniciar servidor y repetir la prueba;
- estado de tests;
- confirmación de que no hubo upstream hacia Grenge;
- confirmación del hash de `base.apk`;
- archivos principales creados con enlaces;
- ruta y estado Git del nuevo repositorio independiente;
- siguiente bloqueo concreto, solo si aún existe.

No afirmes que “funciona” sin evidencia de ejecución del cliente. Distingue siempre entre hallazgo confirmado, inferencia y trabajo pendiente.
