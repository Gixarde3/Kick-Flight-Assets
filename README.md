# Kick Flight Asset Extractor

A complete pipeline for extracting 3D models, textures, and materials from encrypted Unity asset bundles used in the mobile game **Kick Flight**.

## Overview

This tool performs a three-step extraction process to decrypt, decompress, and extract game assets from Kick Flight's custom-encrypted Unity bundles:

1. **Decrypt** - Remove XOR encryption and reconstruct proper Unity bundle headers
2. **Decompress** - Extract LZ4-compressed asset data blocks
3. **Extract** - Parse and export 3D meshes, textures, and materials

The project was reverse-engineered from encrypted Kick Flight game bundles targeting **Unity 2018.4.11f1**.

## Features

- **XOR Decryption**: Removes 7-byte repeating XOR encryption from Unity bundles
- **Header Reconstruction**: Rebuilds proper 53-byte Unity bundle headers
- **LZ4 Decompression**: Decompresses Unity's LZ4-compressed data blocks
- **Asset Extraction**: Exports game assets using UnityPy:
  - 3D meshes (.obj format)
  - Textures (.png format)
  - Material definitions (.txt format)
- **Batch Processing**: Processes hundreds/thousands of bundles automatically
- **Detailed Reporting**: JSON reports with extraction statistics and errors

## Technical Details

### Encryption Scheme
- **Algorithm**: 7-byte repeating XOR key
- **Key**: `[0x6F, 0x0F, 0xFA, 0x46, 0xD3, 0x28, 0x3A]`
- **Target**: UnityFS bundle signature and header data

### Bundle Structure
The tool handles Unity bundles with:
- 53-byte reconstructed headers
- LZ4-compressed block information sections
- Multiple LZ4-compressed or uncompressed data blocks
- Invalid block count in headers (fixed via intelligent parsing)

### Key Discovery
Unity bundle headers contain **unreliable block counts**. The tool parses blocks until hitting invalid flags (>0x003F) instead of trusting the header count.

## Project Structure

```
Kick Flight Asset Extractor/
├── asset_extractor.py          # Main extraction pipeline
├── README.md                    # This file
├── octo_sorted/                 # Sorted input files
│   ├── extraction_report.json  # File sorting report
│   ├── 1_afs2_archives/        # AFS2 archive files
│   ├── 2_cri_audio_video/      # ADX/CRI audio files
│   ├── 3_unity_bundles/        # Encrypted Unity bundles (input)
│   ├── 4_unity_fixed/          # Fixed Unity files
│   └── 5_unknown/              # Unidentified files
└── PIPELINE_OUTPUT/             # Extraction output
    ├── 1_decrypted/            # Decrypted bundles
    ├── 2_raw_assets/           # Decompressed raw asset data
    └── 3_extracted_assets/     # Final extracted assets
        ├── meshes/             # 3D models (.obj)
        ├── textures/           # Texture images (.png)
        └── materials/          # Material definitions (.txt)
```

## Requirements

### Python Version
- Python 3.6 or higher

### Dependencies
```bash
pip install lz4
pip install UnityPy
```

**Required packages:**
- `lz4` - For LZ4 block decompression
- `UnityPy` - For Unity asset parsing and extraction

## Installation

1. **Clone or download this repository**

2. **Install Python dependencies:**
   ```bash
   pip install lz4 UnityPy
   ```

3. **Place encrypted bundles in the input directory:**
   ```
   octo_sorted/3_unity_bundles/
   ```

## Usage

### Basic Usage

Run the complete extraction pipeline:

```bash
python asset_extractor.py
```

The script will automatically:
1. Find all `.bundle` files in `octo_sorted/3_unity_bundles/`
2. Decrypt each bundle
3. Decompress the asset data
4. Extract meshes, textures, and materials

### Output

Extracted assets will be saved to:
- **Meshes**: `PIPELINE_OUTPUT/3_extracted_assets/meshes/`
- **Textures**: `PIPELINE_OUTPUT/3_extracted_assets/textures/`
- **Materials**: `PIPELINE_OUTPUT/3_extracted_assets/materials/`

A detailed JSON report is generated at:
- `PIPELINE_OUTPUT/3_extracted_assets/extraction_results.json`

### Progress Output

The script provides real-time progress updates:
```
================================================================================
KICK FLIGHT ASSET EXTRACTION PIPELINE
================================================================================

Found 2374 encrypted bundles

[1/2374] Processing: bundle_name_001
[100/2374] Processing: bundle_name_100
[200/2374] Processing: bundle_name_200
...

================================================================================
PIPELINE COMPLETE
================================================================================

STEP 1: DECRYPTION
  Success: 2374/2374 (100.0%)

STEP 2: DECOMPRESSION
  Success: 2374/2374 (100.0%)

STEP 3: ASSET EXTRACTION
  Meshes:    1523
  Textures:  3842
  Materials: 1891
  Errors:    12
```

## Configuration

You can modify the following constants in `asset_extractor.py`:

```python
# XOR encryption key (7 bytes, repeating)
XOR_KEY = bytes([0x6F, 0x0F, 0xFA, 0x46, 0xD3, 0x28, 0x3A])

# Input/Output directories
INPUT_BUNDLES = Path('octo_sorted/3_unity_bundles')
OUTPUT_DECRYPTED = Path('PIPELINE_OUTPUT/1_decrypted')
OUTPUT_RAW = Path('PIPELINE_OUTPUT/2_raw_assets')
OUTPUT_MODELS = Path('PIPELINE_OUTPUT/3_extracted_assets')
```

## Extraction Results

The `extraction_results.json` file contains:
```json
{
  "total_bundles": 2374,
  "step1_decrypted": 2374,
  "step2_decompressed": 2374,
  "step3_extracted": {
    "meshes": 1523,
    "textures": 3842,
    "materials": 1891
  },
  "errors": [...]
}
```

## File Naming Convention

Extracted files use the following naming pattern:
- **Meshes**: `mesh_####_<original_name>.obj`
- **Textures**: `texture_####_<original_name>.png`
- **Materials**: `material_####_<original_name>.txt`

Where `####` is a sequential counter (0000, 0001, 0002...).

## Troubleshooting

### No bundles found
- Ensure `.bundle` files are placed in `octo_sorted/3_unity_bundles/`
- Check that the `INPUT_BUNDLES` path is correct

### Decryption failures
- Verify the XOR key is correct for your bundle version
- Check that input files are actually encrypted Unity bundles

### Decompression failures
- Some bundles may have corrupted or non-standard compression
- Check `extraction_results.json` for specific error details

### Asset extraction errors
- Not all Unity asset types are supported
- Some assets may require specific Unity versions
- Check the `errors` array in `extraction_results.json`

## Technical Notes

### Unity Version Compatibility
- Primary target: **Unity 2018.4.11f1**
- May work with other Unity 2018.x versions
- Other versions may require header adjustments

### Block Parsing Algorithm
The tool uses intelligent block parsing instead of trusting header counts:
```python
# Stop conditions:
- Block size > 10MB (invalid)
- All zeros (end marker)
- Flags > 0x0100 (invalid)
```

This solves the "unreliable block count" problem found in Kick Flight bundles.

## Legal Disclaimer

This tool is for **educational and research purposes only**. 

- Respect intellectual property rights
- Only use on content you have legal rights to access
- The authors are not responsible for misuse of this tool
- Game assets remain property of their respective owners

## Credits

- **Author**: Reverse-engineered from Kick Flight game bundles
- **Unity Version**: 2018.4.11f1
- **Libraries**: lz4, UnityPy

## License

This project is provided as-is for educational purposes.

---

**Note**: This tool specifically targets Kick Flight's encryption scheme. It may not work with other Unity games without modification.
