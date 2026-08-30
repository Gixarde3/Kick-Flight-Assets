# Kick Flight — Octo Asset Preservation Pipeline

Pipeline de preservación y extracción para los recursos locales de **Kick Flight** almacenados en la distribución/cache **Octo**. Reconstruye bundles UnityFS, exporta objetos legibles para investigación y conserva los bytes originales para que ningún resultado convertido sustituya a la fuente.

> Uso responsable: trabaja únicamente con copias de archivos que tengas derecho a analizar. Este repositorio procesa contenido local; no implementa autenticación, matchmaking, lógica de batalla, acceso a cuentas ni protocolos del servidor de Grenge.

## Resumen ejecutivo

El entrypoint actual es [asset_extractor.py](asset_extractor.py). Con un solo comando recorre octo_sorted/ y genera:

- bundles UnityFS completos y cargables por UnityPy;
- objetos Unity convertidos a PNG, OBJ, JSON, shaders, fuentes y bytes crudos;
- AnimationClip en JSON más su serialización exacta en .bin;
- streams CRI USM demultiplexados;
- entradas AFS2/AWB en su formato codificado y audio HCA convertido a WAV;
- copias byte a byte de archivos CRI y desconocidos;
- inventarios, hashes SHA-256, reparaciones, advertencias, errores y un reporte agregado.

Los bundles de 1_complete_unityfs/ son la salida autoritativa. Los archivos convertidos son vistas de trabajo para inspección, búsqueda, edición o importación; no reemplazan el bundle original.

## Flujo completo

```mermaid
flowchart TD
    A["octo_sorted/"] --> B["3_unity_bundles/*.bundle"]
    B --> C["Reparar metadata Octo"]
    C --> D["Reconstruir UnityFS estándar"]
    D --> E["Validar con UnityPy"]
    E --> F["Exportar objetos y registrar inventario"]

    A --> G["2_cri_audio_video/*"]
    G --> H["Detectar CRI / USM"]
    H --> I["Demultiplexar streams"]

    A --> J["1_afs2_archives/*"]
    J --> K["Leer AWB y extraer HCA"]
    K --> L["Decodificar WAV con subkey"]

    A --> M["5_unknown/*"]
    M --> N["Preservar sin conversión"]

    F --> O["PIPELINE_OUTPUT_V3/"]
    I --> O
    L --> O
    N --> O
```

### Qué ocurre con un bundle Unity

```mermaid
flowchart LR
    A["Bytes Octo"] --> B["XOR sobre la firma"]
    B --> C["Comprobar UnityFS v6"]
    C --> D["Descomprimir blocks-info con LZ4"]
    D --> E["Probar conteos y complementos válidos"]
    E --> F["Reparar tamaños, flags y nodos"]
    F --> G["Escribir cabecera UnityFS de 50 bytes"]
    G --> H["Conservar payload y nodos CAB/.resS"]
    H --> I["UnityPy.load()"]
    I --> J["Exports + manifests"]
```

### Secuencia de una ejecución V3

```mermaid
sequenceDiagram
    participant U as Usuario
    participant P as asset_extractor.py
    participant R as reconstruct_unity_bundles.py
    participant Y as UnityPy
    participant C as cricodecs
    participant O as PIPELINE_OUTPUT_V3

    U->>P: python asset_extractor.py --input octo_sorted
    P->>R: repair_bundle_bytes(bytes)
    R-->>P: UnityFS completo + reparaciones
    P->>Y: cargar bundle reconstruido
    Y-->>P: objetos Unity
    P->>C: cargar USM / AWB / HCA
    C-->>P: streams y audio decodificado
    P->>O: exports, originales, manifests y report_v3.json
    P-->>U: resumen JSON y código de salida
```

## Datos de entrada: octo_sorted/

El snapshot incluido contiene el inventario registrado en [octo_sorted/extraction_report.json](octo_sorted/extraction_report.json):

| Carpeta | Contenido observado | Cantidad | ¿La consume V3? |
| --- | --- | ---: | --- |
| 1_afs2_archives/ | Contenedores AFS2/AWB con entradas de audio | 12 | Sí |
| 2_cri_audio_video/ | Archivos CRI; el detector identifica el formato real | 148 | Sí |
| 3_unity_bundles/ | Bundles UnityFS con formato Octo | 2374 | Sí |
| 4_unity_fixed/ | Archivos Unity ya reparados de una etapa anterior | 644 | No, queda como referencia manual |
| 5_unknown/ | Archivos que no se clasificaron | 46 | Sí, se preservan sin conversión |

La cantidad es propia de este snapshot y puede cambiar si se reemplaza el dump. El pipeline principal busca los bundles directamente en 3_unity_bundles/*.bundle; no hace una búsqueda recursiva ni usa automáticamente 4_unity_fixed/.

## Requisitos

- Python **3.10 o superior**. El código usa anotaciones y sintaxis moderna de Python; 
- Espacio suficiente para bundles completos, conversiones y copias preservadas. El procesamiento puede generar muchos archivos.
- Dependencias de [requirements.txt](requirements.txt):

  - lz4 para blocks-info y bloques Unity comprimidos;
  - UnityPy para leer e inventariar objetos Unity;
  - cricodecs para CRI USM, AFS2/AWB, HCA y WAV.

El entorno local con el que se verificó este README usa Python 3.14.5, lz4 4.4.5 y UnityPy 1.25.3.

## Instalación

Desde la raíz del repositorio:

### Windows PowerShell

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Si PowerShell bloquea la activación, puede usarse el intérprete del entorno directamente:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe asset_extractor.py
```

### Git Bash o Linux/macOS

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Ejecución recomendada: pipeline V3 completo

Con el entorno virtual activo y situándose en la raíz del proyecto:

```bash
python asset_extractor.py --input octo_sorted --output PIPELINE_OUTPUT_V3
```

Los valores anteriores coinciden con los defaults del código, por lo que también funciona:

```bash
python asset_extractor.py
```

Para una prueba corta, --limit N toma los primeros N elementos de **cada categoría** de entrada, no N elementos totales:

```bash
python asset_extractor.py --input octo_sorted --output PIPELINE_OUTPUT_V3_SMOKE --limit 1
```

Opciones disponibles:

| Opción | Default | Descripción |
| --- | --- | --- |
| --input PATH | octo_sorted | Raíz con las cinco carpetas clasificadas |
| --output PATH | PIPELINE_OUTPUT_V3 | Directorio donde se escribe todo el resultado |
| --limit N | sin límite | Procesa los primeros N archivos por categoría |

El proceso continúa con los demás archivos aunque encuentre un fallo. Al terminar:

- código de salida 0: no hubo errores registrados;
- código de salida 1: hubo uno o más errores; revisar manifests/errors.json;
- las advertencias no hacen fallar la ejecución, pero quedan en manifests/warnings.json.

## Reconstrucción especializada de UnityFS

[reconstruct_unity_bundles.py](reconstruct_unity_bundles.py) es el módulo de bajo nivel para reparar únicamente los bundles Unity de octo_sorted/3_unity_bundles/. asset_extractor.py ya usa esta misma lógica internamente, así que no es necesario ejecutar ambos para obtener la salida V3.

Ejecución completa de la etapa especializada:

```bash
python reconstruct_unity_bundles.py
```

Ejecución de prueba y ejecución rápida sin validación UnityPy:

```bash
python reconstruct_unity_bundles.py --limit 10
python reconstruct_unity_bundles.py --no-verify
```

Con rutas explícitas:

```bash
python reconstruct_unity_bundles.py \
  --input octo_sorted/3_unity_bundles \
  --output PIPELINE_OUTPUT_V2/1_reconstructed_bundles
```

Esta herramienta:

1. comprueba la firma XOR y exige UnityFS format 6;
2. descomprime la metadata LZ4;
3. reconstruye la tabla de bloques y el directorio de nodos;
4. conserva nodos CAB-*, .resS y otros sidecars;
5. verifica cada salida con UnityPy salvo que se pase --no-verify;
6. escribe PIPELINE_OUTPUT_V2/bundle_rebuild_report.json con tamaños, hashes, nodos, reparaciones, objetos y errores.

## Estructura de salida V3

```text
PIPELINE_OUTPUT_V3/
├── 1_complete_unityfs/
│   └── *.bundle                         # bundles UnityFS completos y reparados
├── 2_converted_unity_assets/
│   ├── images/
│   │   ├── Texture2D/                   # PNG
│   │   ├── Sprite/                      # PNG
│   │   └── Cubemap/                     # PNG cuando UnityPy puede convertirlo
│   ├── meshes/                          # OBJ
│   ├── structured/                      # JSON por tipo Unity
│   ├── animation_raw/                   # bytes exactos de AnimationClip
│   ├── structured_raw/                  # bytes de tipos estructurados
│   ├── text_assets/                     # TextAsset como bytes originales
│   ├── shaders/                         # shaders exportados
│   ├── fonts/                           # datos de fuentes
│   └── unconverted_raw/                 # fallback ante conversión incompleta
├── 3_cri_media/
│   ├── usm_demux/                       # streams extraídos de USM
│   └── awb_entries/                     # HCA y WAV por entrada AWB
├── 4_preserved_originals/
│   ├── cri_loose/                       # copias de CRI sueltos
│   ├── afs2_awb/                        # copias de AFS2 originales
│   └── unknown/                         # copias de archivos desconocidos
├── manifests/
│   ├── unity_objects.jsonl              # un registro por objeto Unity
│   ├── bundles.json                     # bundles, nodos, hashes y reparaciones
│   ├── animations.json                  # índice de AnimationClip
│   ├── media.json                       # índice de CRI y AFS2/AWB
│   ├── errors.json                      # errores por etapa y archivo
│   └── warnings.json                    # conversiones con fallback o warning
└── report_v3.json                       # resumen agregado
```

### Exportaciones por tipo

| Tipo detectado | Salida principal | Preservación adicional |
| --- | --- | --- |
| Texture2D, Sprite, Cubemap | PNG | .bin si las dimensiones son inválidas |
| Mesh | OBJ | fallback .bin si falla la conversión |
| Material, AnimatorController, AnimatorOverrideController, Avatar, MonoBehaviour | JSON de typetree | bytes serializados cuando aplica |
| AnimationClip | JSON de typetree | .bin exacto e índice animations.json |
| TextAsset | .bin | se restaura el byte original mediante surrogateescape |
| Shader | .shader | fallback .bin si UnityPy no lo exporta |
| Font | .font | bytes de m_FontData |
| USM | streams demultiplexados | copia original en 4_preserved_originals/cri_loose/ |
| AWB/HCA | HCA codificado y WAV | copia original del AFS2 |
| Desconocido | — | copia byte a byte |

## Hallazgos: cifrado y ofuscación de Octo

### 1. XOR repetitivo de 7 bytes

La firma inicial de los bundles no aparece como UnityFS en bruto. La implementación aplica una clave XOR repetitiva a los primeros siete bytes:

```text
6F 0F FA 46 D3 28 3A
```

Para cada posición i:

```text
decoded[i] = raw[i] XOR key[i mod 7]
```

En el sample incluido, esa operación produce exactamente 55 6E 69 74 79 46 53, es decir, UnityFS.

Esto es ofuscación reversible, no cifrado criptográfico robusto: la clave es corta, repetitiva y está embebida en el código. No hay evidencia en estos scripts de AES, RSA, intercambio de claves, keystore o una capa criptográfica general para el payload.

### 2. Cabecera Octo distinta de la cabecera UnityFS estándar

Después de la firma, el prefijo almacenado por Octo no se puede pasar directamente a UnityPy. El reconstruidor:

- recupera el formato UnityFS 6;
- toma la información de versión/revisión del encabezado de entrada;
- reconstruye una cabecera UnityFS estándar de 50 bytes;
- establece flags 0x00000003, que indican blocks-info LZ4;
- recalcula el tamaño total con la metadata comprimida reconstruida y el payload original.

El payload de datos no se vuelve a cifrar ni se reinterpreta como un formato nuevo; se conserva y se vuelve a asociar con su directorio de nodos.

### 3. Metadata parcialmente dañada u ofuscada

La reparación no confía ciegamente en los contadores del archivo. Evalúa candidatos y acepta únicamente una estructura consistente:

- el block_count original o una variante con un byte complementado, byte XOR 0xFF;
- node_count con la misma estrategia de candidato;
- flags de bloque dentro de {0, 1, 2, 3};
- flags de nodo dentro de {0, 1, 2, 4};
- suma de tamaños comprimidos igual al tamaño real del payload;
- nodos contiguos, comenzando en offset 0 y terminando en el tamaño total sin comprimir;
- nombres de nodo UTF-8 y consumo exacto de blocks-info.

Cuando el bloque de información LZ4 falla, también se prueba una reparación puntual del byte 5 de esa sección. Cada cambio queda registrado en repairs y en manifests/bundles.json o bundle_rebuild_report.json.

La consecuencia importante es que block_count no es una fuente de verdad suficiente. La estructura completa —tamaños, flags, offsets, nombres y tamaño del payload— funciona como comprobación de integridad y evita adivinar cuando hay más de una solución posible.

### 4. Sidecars Unity y por qué importa el directorio de nodos

Un bundle UnityFS no es solamente la concatenación de bloques descomprimidos. Su directorio relaciona el archivo serializado con recursos externos como CAB-* y .resS. La etapa antigua de extracción podía producir un stream útil, pero perdía esa relación.

La reconstrucción actual conserva el directorio completo. Por eso los bundles de 1_complete_unityfs/ son mejores candidatos para abrirse con UnityPy o investigarse con un cliente compatible que los streams crudos de etapas anteriores.

### 5. HCA no es la misma capa que XOR de Octo

El audio HCA se encuentra dentro de entradas AWB. cricodecs lee el subkey del contenedor AWB y lo usa al decodificar a WAV. Esa protección/decodificación pertenece al formato de audio CRI y debe analizarse por separado de la ofuscación XOR y metadata de los bundles Octo.

## Diferencia entre las etapas y qué conserva cada una

```mermaid
flowchart TD
    A["Octo original"] --> B["V2: reconstrucción UnityFS"]
    A --> C["V3: preservación integral"]
    B --> B1["Bundles Unity completos"]
    B --> B2["bundle_rebuild_report.json"]
    C --> C1["Bundles + objetos convertidos"]
    C --> C2["CRI / AFS2 / HCA / WAV"]
    C --> C3["Originales + manifests + report_v3.json"]
    A -.-> D["V1/legacy: stream raw; no usar como fuente autoritativa"]
```

| Etapa | Entry point | Uso principal | Salida |
| --- | --- | --- | --- |
| V3 | asset_extractor.py | Resultado integral en una sola ejecución | PIPELINE_OUTPUT_V3/ |
| V2 | reconstruct_unity_bundles.py | Diagnóstico/reconstrucción UnityFS dedicada | PIPELINE_OUTPUT_V2/ |
| Legacy | scripts o outputs históricos | Compatibilidad con investigaciones previas | No usar como fuente de verdad |

## Verificación rápida

La forma más representativa de comprobar instalación, reparación, UnityPy y CRI sin procesar todo el dump es:

```bash
python asset_extractor.py --input octo_sorted --output PIPELINE_OUTPUT_V3_SMOKE --limit 1
```

Una ejecución correcta debe crear PIPELINE_OUTPUT_V3_SMOKE/report_v3.json y dejar errors igual a 0. En el snapshot local, la prueba de un elemento reconstruyó un bundle, cargó objetos Unity, demultiplexó un USM y produjo WAV desde una entrada HCA.

También puede verificarse solo UnityFS:

```bash
python reconstruct_unity_bundles.py \
  --input octo_sorted/3_unity_bundles \
  --output PIPELINE_OUTPUT_V2_SMOKE/1_reconstructed_bundles \
  --limit 1
```

### Suite de pruebas

Las pruebas requieren pytest, que no forma parte de requirements.txt:

```bash
python -m pip install pytest
python -m pytest -q
```

Las pruebas de pipeline importan V3Pipeline desde asset_extractor.py; la prueba de reconstrucción usa directamente reconstruct_unity_bundles.py.

## Troubleshooting

### ModuleNotFoundError: lz4, UnityPy o cricodecs

Comprueba que el entorno virtual está activo e instala las dependencias con el mismo intérprete que ejecutará el pipeline:

```bash
python -m pip install -r requirements.txt
python -c "import lz4, UnityPy, cricodecs; print('dependencias OK')"
```

### no .bundle files found

El reconstruidor especializado espera octo_sorted/3_unity_bundles/*.bundle. Revisa la ruta y que estés ejecutando desde la raíz del repositorio, o pasa --input explícitamente.

### Hay archivos en errors.json

El batch continúa por diseño. Busca el campo stage para distinguir unity_bundle, cri_loose, afs2_awb, unity_typetree o una conversión individual. El archivo original de entrada no se modifica; la salida problemática queda registrada.

### Hay un .bin en unconverted_raw/

No significa necesariamente pérdida de datos. Es el fallback de preservación cuando UnityPy no puede convertir un objeto, una imagen tiene dimensiones inválidas o un typetree no se puede leer. Usa unity_objects.jsonl para localizar el bundle, path_id, tipo y nombre.

### El proceso tarda o consume mucho espacio

Empieza con --limit 1 o --limit 10, usa un --output temporal y confirma el resultado antes de lanzar la ejecución completa. --no-verify acelera únicamente la herramienta especializada V2; no desactiva las reparaciones.

### El archivo convertido no es suficiente para reconstruir un cliente

Usa 1_complete_unityfs/ y los originales preservados. Un PNG, OBJ o JSON es una representación de investigación y puede perder información específica de Unity; el bundle completo y los .bin serializados son la referencia primaria.

## Convenciones y reproducibilidad

- Las salidas se organizan por bundle, archivo de assets y path_id para evitar colisiones de nombres.
- Los nombres legibles se sanitizan para impedir separadores de ruta y metacaracteres.
- Los manifests registran hashes SHA-256 de los bundles reconstruidos y de los medios preservados.
- unity_objects.jsonl usa un registro JSON por línea, adecuado para búsquedas incrementales sin cargar todo en memoria.
- Los reportes se escriben en UTF-8 y conservan bytes no UTF-8 mediante Base64 o surrogateescape según el tipo de objeto.
- PIPELINE_OUTPUT_V3/ está ignorado por Git. Conviene usar un directorio de salida separado para no mezclar resultados nuevos con artefactos legacy.

## Alcance y límites

Este proyecto es una herramienta de análisis y preservación de contenido. No:

- reconstruye el backend, catálogo Octo, cuentas, autenticación o matchmaking;
- emula la simulación de batalla ni crea un servidor de Kick Flight;
- repaqueta automáticamente un APK o genera un proyecto Unity listo para compilar;
- garantiza que todos los objetos Unity tengan una conversión de alta fidelidad;
- interpreta semánticamente cada MonoBehaviour o asset desconocido.

El objetivo es conservar la evidencia original, producir representaciones útiles y dejar trazabilidad suficiente para continuar la investigación de forma reproducible.

## Créditos técnicos

- **Proyecto:** Kick Flight Asset Extractor
- **Target Unity observado:** 2018.4.11f1
- **Formato de bundle:** UnityFS format 6
- **Compresión:** LZ4 para blocks-info y bloques Unity según metadata
- **Media:** CRI USM, AFS2/AWB, HCA y WAV mediante cricodecs
- **Parser Unity:** UnityPy
- **Autor original indicado en el proyecto:** Gixarde3

---

# Kick Flight — Octo Asset Preservation Pipeline (English)

Preservation and extraction pipeline for local **Kick Flight** resources stored in the **Octo** distribution/cache. It rebuilds UnityFS bundles, exports research-friendly objects, and preserves the original bytes so that no converted result replaces the source material.

> Responsible use: work only with copies of files you are authorized to analyze. This repository processes local content; it does not implement authentication, matchmaking, battle logic, account access, or Grenge server protocols.

## Executive summary

The current entry point is [asset_extractor.py](asset_extractor.py). With one command it walks through octo_sorted/ and produces:

- complete UnityFS bundles that can be loaded by UnityPy;
- Unity objects converted to PNG, OBJ, JSON, shaders, fonts, and raw bytes;
- AnimationClip data as JSON plus its exact serialized representation in .bin;
- demultiplexed CRI USM streams;
- AFS2/AWB entries in their encoded format and HCA audio decoded to WAV;
- byte-for-byte copies of CRI and unknown files;
- inventories, SHA-256 hashes, repairs, warnings, errors, and an aggregate report.

The bundles in 1_complete_unityfs/ are the authoritative output. Converted files are working views for inspection, searching, editing, or importing; they do not replace the original bundle.

## Complete workflow

```mermaid
flowchart TD
    A["octo_sorted/"] --> B["3_unity_bundles/*.bundle"]
    B --> C["Repair Octo metadata"]
    C --> D["Rebuild standard UnityFS"]
    D --> E["Validate with UnityPy"]
    E --> F["Export objects and write inventory"]

    A --> G["2_cri_audio_video/*"]
    G --> H["Detect CRI / USM"]
    H --> I["Demultiplex streams"]

    A --> J["1_afs2_archives/*"]
    J --> K["Read AWB and extract HCA"]
    K --> L["Decode WAV with subkey"]

    A --> M["5_unknown/*"]
    M --> N["Preserve without conversion"]

    F --> O["PIPELINE_OUTPUT_V3/"]
    I --> O
    L --> O
    N --> O
```

### What happens to a Unity bundle

```mermaid
flowchart LR
    A["Octo bytes"] --> B["XOR the signature"]
    B --> C["Check UnityFS v6"]
    C --> D["Decompress blocks-info with LZ4"]
    D --> E["Try valid counts and complements"]
    E --> F["Repair sizes, flags, and nodes"]
    F --> G["Write 50-byte UnityFS header"]
    G --> H["Keep payload and CAB/.resS nodes"]
    H --> I["UnityPy.load()"]
    I --> J["Exports + manifests"]
```

### V3 execution sequence

```mermaid
sequenceDiagram
    participant U as User
    participant P as asset_extractor.py
    participant R as reconstruct_unity_bundles.py
    participant Y as UnityPy
    participant C as cricodecs
    participant O as PIPELINE_OUTPUT_V3

    U->>P: python asset_extractor.py --input octo_sorted
    P->>R: repair_bundle_bytes(bytes)
    R-->>P: Complete UnityFS + repairs
    P->>Y: Load rebuilt bundle
    Y-->>P: Unity objects
    P->>C: Load USM / AWB / HCA
    C-->>P: Streams and decoded audio
    P->>O: Exports, originals, manifests, and report_v3.json
    P-->>U: JSON summary and exit code
```

## Input data: octo_sorted/

The included snapshot contains the inventory recorded in [octo_sorted/extraction_report.json](octo_sorted/extraction_report.json):

| Folder | Observed content | Count | Consumed by V3? |
| --- | --- | ---: | --- |
| 1_afs2_archives/ | AFS2/AWB containers with audio entries | 12 | Yes |
| 2_cri_audio_video/ | CRI files; the detector identifies the actual format | 148 | Yes |
| 3_unity_bundles/ | UnityFS bundles using the Octo layout | 2374 | Yes |
| 4_unity_fixed/ | Unity files repaired by an earlier stage | 644 | No, manual reference only |
| 5_unknown/ | Files that were not classified | 46 | Yes, preserved without conversion |

These counts belong to this snapshot and may change when the dump is replaced. The main pipeline looks for bundles directly in 3_unity_bundles/*.bundle; it does not search recursively and does not automatically use 4_unity_fixed/.

## Requirements

- Python **3.10 or newer**. The code uses modern Python annotations and syntax; Python 3.6, mentioned in older documentation, is no longer supported.
- Enough disk space for complete bundles, converted assets, and preserved copies. Processing can produce a large number of files.
- The dependencies listed in [requirements.txt](requirements.txt):

  - lz4 for blocks-info and compressed Unity blocks;
  - UnityPy for reading and inventorying Unity objects;
  - cricodecs for CRI USM, AFS2/AWB, HCA, and WAV.

This README was verified locally with Python 3.14.5, lz4 4.4.5, and UnityPy 1.25.3.

## Installation

Run the following commands from the repository root.

### Windows PowerShell

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, use the virtual-environment interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe asset_extractor.py
```

### Git Bash or Linux/macOS

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Recommended execution: complete V3 pipeline

With the virtual environment active and the shell located at the project root:

```bash
python asset_extractor.py --input octo_sorted --output PIPELINE_OUTPUT_V3
```

The values above match the code defaults, so this also works:

```bash
python asset_extractor.py
```

For a short smoke run, --limit N takes the first N items from **each input category**, not N items in total:

```bash
python asset_extractor.py --input octo_sorted --output PIPELINE_OUTPUT_V3_SMOKE --limit 1
```

Available options:

| Option | Default | Description |
| --- | --- | --- |
| --input PATH | octo_sorted | Root containing the five classified folders |
| --output PATH | PIPELINE_OUTPUT_V3 | Directory where the complete result is written |
| --limit N | no limit | Process the first N files in each category |

The process continues with the remaining files after an individual failure. At the end:

- exit code 0 means no errors were recorded;
- exit code 1 means one or more errors occurred; inspect manifests/errors.json;
- warnings do not fail the run, but are stored in manifests/warnings.json.

## Specialized UnityFS reconstruction

[reconstruct_unity_bundles.py](reconstruct_unity_bundles.py) is the low-level module for repairing only the Unity bundles in octo_sorted/3_unity_bundles/. asset_extractor.py already uses the same logic internally, so running both is not required to obtain the V3 output.

Run the specialized stage against the complete input:

```bash
python reconstruct_unity_bundles.py
```

Run a short test or skip UnityPy validation for a faster pass:

```bash
python reconstruct_unity_bundles.py --limit 10
python reconstruct_unity_bundles.py --no-verify
```

With explicit paths:

```bash
python reconstruct_unity_bundles.py \
  --input octo_sorted/3_unity_bundles \
  --output PIPELINE_OUTPUT_V2/1_reconstructed_bundles
```

This tool:

1. checks the XOR signature and requires UnityFS format 6;
2. decompresses the LZ4 metadata;
3. rebuilds the block table and node directory;
4. preserves CAB-*, .resS, and other sidecar nodes;
5. validates every output with UnityPy unless --no-verify is passed;
6. writes PIPELINE_OUTPUT_V2/bundle_rebuild_report.json with sizes, hashes, nodes, repairs, objects, and errors.

## V3 output structure

```text
PIPELINE_OUTPUT_V3/
├── 1_complete_unityfs/
│   └── *.bundle                         # complete repaired UnityFS bundles
├── 2_converted_unity_assets/
│   ├── images/
│   │   ├── Texture2D/                   # PNG
│   │   ├── Sprite/                      # PNG
│   │   └── Cubemap/                     # PNG when UnityPy can convert it
│   ├── meshes/                          # OBJ
│   ├── structured/                      # JSON by Unity type
│   ├── animation_raw/                   # exact AnimationClip bytes
│   ├── structured_raw/                  # serialized structured-type bytes
│   ├── text_assets/                     # TextAsset as original bytes
│   ├── shaders/                         # exported shaders
│   ├── fonts/                           # font data
│   └── unconverted_raw/                 # fallback for incomplete conversions
├── 3_cri_media/
│   ├── usm_demux/                       # streams extracted from USM
│   └── awb_entries/                     # HCA and WAV per AWB entry
├── 4_preserved_originals/
│   ├── cri_loose/                       # copies of loose CRI files
│   ├── afs2_awb/                        # copies of original AFS2 files
│   └── unknown/                         # copies of unknown files
├── manifests/
│   ├── unity_objects.jsonl              # one record per Unity object
│   ├── bundles.json                     # bundles, nodes, hashes, and repairs
│   ├── animations.json                  # AnimationClip index
│   ├── media.json                       # CRI and AFS2/AWB index
│   ├── errors.json                      # errors by stage and file
│   └── warnings.json                    # fallbacks and conversion warnings
└── report_v3.json                       # aggregate summary
```

### Exported types

| Detected type | Primary output | Additional preservation |
| --- | --- | --- |
| Texture2D, Sprite, Cubemap | PNG | .bin when dimensions are invalid |
| Mesh | OBJ | .bin fallback when conversion fails |
| Material, AnimatorController, AnimatorOverrideController, Avatar, MonoBehaviour | Typetree JSON | serialized bytes when applicable |
| AnimationClip | Typetree JSON | exact .bin and animations.json index |
| TextAsset | .bin | original bytes restored through surrogateescape |
| Shader | .shader | .bin fallback when UnityPy cannot export it |
| Font | .font | m_FontData bytes |
| USM | demultiplexed streams | original copy under 4_preserved_originals/cri_loose/ |
| AWB/HCA | encoded HCA and WAV | original AFS2 copy |
| Unknown | — | byte-for-byte copy |

## Findings: Octo encryption and obfuscation

### 1. Seven-byte repeating XOR

The initial bundle signature does not appear as UnityFS in the raw bytes. The implementation applies a repeating XOR key to the first seven bytes:

```text
6F 0F FA 46 D3 28 3A
```

For each position i:

```text
decoded[i] = raw[i] XOR key[i mod 7]
```

In the included sample, this produces exactly 55 6E 69 74 79 46 53, which is UnityFS.

This is reversible obfuscation, not strong cryptographic encryption: the key is short, repetitive, and embedded in the code. There is no evidence in these scripts of AES, RSA, key exchange, a keystore, or a general cryptographic layer for the payload.

### 2. Octo header differs from a standard UnityFS header

After the signature, the Octo-stored prefix cannot be passed directly to UnityPy. The rebuilder:

- restores UnityFS format 6;
- takes version and revision information from the input header;
- rebuilds a standard 50-byte UnityFS header;
- sets flags 0x00000003, indicating LZ4 blocks-info;
- recalculates the total size from the rebuilt compressed metadata and original payload.

The data payload is not re-encrypted or interpreted as a new format; it is preserved and re-associated with its node directory.

### 3. Partially damaged or obfuscated metadata

The repair logic does not blindly trust the file counters. It evaluates candidates and accepts only a structurally consistent layout:

- the original block_count or a one-byte-complement variant, byte XOR 0xFF;
- node_count using the same candidate strategy;
- block flags within {0, 1, 2, 3};
- node flags within {0, 1, 2, 4};
- the sum of compressed sizes equals the actual payload size;
- nodes are contiguous, begin at offset 0, and end at the total uncompressed size;
- node names are UTF-8 and blocks-info is consumed exactly.

If the LZ4 information block fails, the implementation also tries a targeted repair of byte 5 in that section. Every change is recorded in repairs and in manifests/bundles.json or bundle_rebuild_report.json.

The important consequence is that block_count is not a sufficient source of truth. The complete structure — sizes, flags, offsets, names, and payload size — acts as an integrity check and avoids guessing when multiple solutions are possible.

### 4. Unity sidecars and why the node directory matters

A UnityFS bundle is not merely the concatenation of decompressed blocks. Its directory associates the serialized file with external resources such as CAB-* and .resS. The older extraction stage could produce a useful raw stream, but it lost that relationship.

The current reconstruction preserves the complete directory. That makes the bundles in 1_complete_unityfs/ better candidates for UnityPy or compatible-client research than the raw streams produced by earlier stages.

### 5. HCA is a separate layer from Octo XOR

HCA audio is stored inside AWB entries. cricodecs reads the container subkey and uses it to decode WAV audio. That protection/decoding belongs to the CRI audio format and must be analyzed separately from the Octo XOR and metadata obfuscation.

## Difference between stages and what each preserves

```mermaid
flowchart TD
    A["Original Octo data"] --> B["V2: UnityFS reconstruction"]
    A --> C["V3: full preservation"]
    B --> B1["Complete Unity bundles"]
    B --> B2["bundle_rebuild_report.json"]
    C --> C1["Bundles + converted objects"]
    C --> C2["CRI / AFS2 / HCA / WAV"]
    C --> C3["Originals + manifests + report_v3.json"]
    A -.-> D["V1/legacy: raw stream; not authoritative"]
```

| Stage | Entry point | Main use | Output |
| --- | --- | --- | --- |
| V3 | asset_extractor.py | Complete result in a single run | PIPELINE_OUTPUT_V3/ |
| V2 | reconstruct_unity_bundles.py | Dedicated UnityFS diagnostics/reconstruction | PIPELINE_OUTPUT_V2/ |
| Legacy | historical scripts or outputs | Compatibility with earlier research | Do not use as the source of truth |

## Quick verification

The most representative way to verify installation, repair, UnityPy, and CRI without processing the entire dump is:

```bash
python asset_extractor.py --input octo_sorted --output PIPELINE_OUTPUT_V3_SMOKE --limit 1
```

A successful run creates PIPELINE_OUTPUT_V3_SMOKE/report_v3.json and leaves errors equal to 0. In the local snapshot, the one-item run rebuilt a bundle, loaded Unity objects, demultiplexed a USM, and produced WAV audio from an HCA entry.

UnityFS can also be checked independently:

```bash
python reconstruct_unity_bundles.py \
  --input octo_sorted/3_unity_bundles \
  --output PIPELINE_OUTPUT_V2_SMOKE/1_reconstructed_bundles \
  --limit 1
```

### Test suite

The tests require pytest, which is not part of requirements.txt:

```bash
python -m pip install pytest
python -m pytest -q
```

The pipeline tests import V3Pipeline from asset_extractor.py; the reconstruction test uses reconstruct_unity_bundles.py directly.

## Troubleshooting

### ModuleNotFoundError: lz4, UnityPy, or cricodecs

Make sure the virtual environment is active and install dependencies with the same interpreter that will run the pipeline:

```bash
python -m pip install -r requirements.txt
python -c "import lz4, UnityPy, cricodecs; print('dependencies OK')"
```

### no .bundle files found

The specialized rebuilder expects octo_sorted/3_unity_bundles/*.bundle. Check the path and make sure you are running from the repository root, or pass --input explicitly.

### errors.json contains entries

The batch continues by design. Use the stage field to distinguish unity_bundle, cri_loose, afs2_awb, unity_typetree, or an individual conversion. Input files are not modified; the problematic output is recorded.

### A .bin file appears in unconverted_raw/

This does not necessarily mean data was lost. It is the preservation fallback used when UnityPy cannot convert an object, an image has invalid dimensions, or a typetree cannot be read. Use unity_objects.jsonl to locate the bundle, path_id, type, and name.

### The process is slow or uses a lot of disk space

Start with --limit 1 or --limit 10, use a temporary --output directory, and confirm the result before launching the complete run. --no-verify speeds up only the specialized V2 tool; it does not disable repairs.

### The converted file is not enough to rebuild a client

Use 1_complete_unityfs/ and the preserved originals. A PNG, OBJ, or JSON file is a research representation and may lose Unity-specific information; the complete bundle and serialized .bin files are the primary reference.

## Reproducibility conventions

- Outputs are organized by bundle, assets file, and path_id to avoid name collisions.
- Readable names are sanitized to prevent path separators and metacharacters.
- Manifests record SHA-256 hashes for rebuilt bundles and preserved media.
- unity_objects.jsonl stores one JSON record per line, which is suitable for incremental searches without loading the entire file into memory.
- Reports are written as UTF-8 and preserve non-UTF-8 bytes through Base64 or surrogateescape, depending on the object type.
- PIPELINE_OUTPUT_V3/ is ignored by Git. Use a separate output directory to avoid mixing new results with legacy artifacts.

## Scope and limitations

This project is a content analysis and preservation tool. It does not:

- rebuild the backend, Octo catalog, accounts, authentication, or matchmaking;
- emulate battle simulation or create a Kick Flight server;
- automatically repackage an APK or generate a ready-to-build Unity project;
- guarantee a high-fidelity conversion for every Unity object;
- semantically interpret every MonoBehaviour or unknown asset.

The goal is to preserve the original evidence, produce useful representations, and leave enough traceability for further reproducible research.

## Technical credits

- **Project:** Kick Flight Asset Extractor
- **Observed Unity target:** 2018.4.11f1
- **Bundle format:** UnityFS format 6
- **Compression:** LZ4 for blocks-info and Unity blocks according to metadata
- **Media:** CRI USM, AFS2/AWB, HCA, and WAV through cricodecs
- **Unity parser:** UnityPy
- **Original author listed in the project:** Gixarde3
