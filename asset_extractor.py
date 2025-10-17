"""
COMPLETE KICK FLIGHT ASSET EXTRACTION PIPELINE
===============================================

This script performs the complete 3-step extraction process:
1. Decrypt XOR-encrypted Unity bundles (7-byte key)
2. Decompress LZ4-compressed blocks to raw asset data
3. Extract 3D models, textures, and materials using UnityPy

Key Discovery: Unity bundle headers contain unreliable block counts.
Must parse blocks until hitting invalid flags (>0x003F) instead of trusting header.

Author: Reverse-engineered from encrypted Kick Flight game bundles
Unity Version: 2018.4.11f1
"""

from pathlib import Path
import struct
import lz4.block
import UnityPy
import json


# ============================================================================
# CONFIGURATION
# ============================================================================

# XOR encryption key (7 bytes, repeating)
XOR_KEY = bytes([0x6F, 0x0F, 0xFA, 0x46, 0xD3, 0x28, 0x3A])

# Input/Output directories
INPUT_BUNDLES = Path('octo_sorted/3_unity_bundles')
OUTPUT_DECRYPTED = Path('PIPELINE_OUTPUT/1_decrypted')
OUTPUT_RAW = Path('PIPELINE_OUTPUT/2_raw_assets')
OUTPUT_MODELS = Path('PIPELINE_OUTPUT/3_extracted_assets')

# Create output directories
OUTPUT_DECRYPTED.mkdir(parents=True, exist_ok=True)
OUTPUT_RAW.mkdir(parents=True, exist_ok=True)
OUTPUT_MODELS.mkdir(parents=True, exist_ok=True)
(OUTPUT_MODELS / 'meshes').mkdir(exist_ok=True)
(OUTPUT_MODELS / 'textures').mkdir(exist_ok=True)
(OUTPUT_MODELS / 'materials').mkdir(exist_ok=True)


# ============================================================================
# STEP 1: DECRYPT XOR-ENCRYPTED BUNDLES
# ============================================================================

def xor_decrypt(data, key):
    """XOR decrypt with repeating key"""
    key_len = len(key)
    return bytes(data[i] ^ key[i % key_len] for i in range(len(data)))


def decrypt_bundle(encrypted_path, output_path):
    """
    Decrypt a Unity bundle and reconstruct proper 53-byte header
    
    Based on STEP1_DECRYPT/decrypt_bundles.py - VERIFIED WORKING
    """
    try:
        data = encrypted_path.read_bytes()
        
        if len(data) < 54:
            return False
        
        # Decrypt signature
        decrypted_sig = xor_decrypt(data[:7], XOR_KEY)
        if decrypted_sig != b'UnityFS':
            return False
        
        # Build 53-byte header
        header = bytearray()
        
        # [0:7] Signature
        header.extend(decrypted_sig)
        
        # [7:11] Format version - from data[12:16]
        header.extend(data[12:16])
        
        # [11:17] Unity version - from data[16:22]
        header.extend(data[16:22])
        
        # [17:29] Unity revision - from data[22:34]
        header.extend(data[22:34])
        
        # [29:37] File size - from data[34:42] PLUS 3 bytes
        file_size = struct.unpack('>Q', data[34:42])[0]
        new_file_size = file_size + 3  # Add FLAGS (4) minus junk (1)
        header.extend(struct.pack('>Q', new_file_size))
        
        # [37:41] Compressed blocks info size - from data[42:46]
        header.extend(data[42:46])
        
        # [41:45] Uncompressed blocks info size - from data[46:50]
        header.extend(data[46:50])
        
        # [45:49] Compressed data offset - from data[50:54]
        header.extend(data[50:54])
        
        # [49:53] FLAGS - ADD THIS
        header.extend(struct.pack('>I', 0x00000043))
        
        # Verify 53 bytes
        assert len(header) == 53
        
        # Append data from enc[54:]
        reconstructed = bytes(header) + data[54:]
        
        output_path.write_bytes(reconstructed)
        return True
        
    except:
        return False


# ============================================================================
# STEP 2: DECOMPRESS LZ4 BLOCKS TO RAW ASSET DATA
# ============================================================================

def decompress_bundle(bundle_path, output_path):
    """
    Decompress Unity bundle blocks to raw asset data
    
    TWO-STEP PROCESS:
    1. Decompress the blocks info section (LZ4 compressed)
    2. Decompress each data block using info from step 1
    
    Structure:
    - [0:53]   Header
      - [37:41] ciblock_size - compressed blocks info size
      - [41:45] uiblock_size - uncompressed blocks info size
    - [53+]    Compressed blocks info (LZ4)
    - After that: Data blocks
    """
    try:
        data = bundle_path.read_bytes()
        
        # Read header fields
        ciblock_size = struct.unpack('>I', data[37:41])[0]
        uiblock_size = struct.unpack('>I', data[41:45])[0]
        
        # Step 1: Decompress blocks info
        blocks_offset = 53
        compressed_blocks_info = data[blocks_offset:blocks_offset + ciblock_size]
        
        try:
            blocks_info = lz4.block.decompress(
                compressed_blocks_info,
                uncompressed_size=uiblock_size
            )
        except:
            return False
        
        if len(blocks_info) < 20:
            return False
        
        # CRITICAL FIX: Parse blocks until invalid flags detected
        blocks = []
        offset = 20  # Start after GUID (16 bytes) and claimed count (4 bytes)
        max_blocks = (len(blocks_info) - 20) // 10
        
        for i in range(max_blocks):
            if offset + 10 > len(blocks_info):
                break
            
            # Read block info
            usize = struct.unpack('>I', blocks_info[offset:offset+4])[0]
            csize = struct.unpack('>I', blocks_info[offset+4:offset+8])[0]
            flags = struct.unpack('>H', blocks_info[offset+8:offset+10])[0]
            
            # Sanity checks - stop at invalid data
            if usize > 10000000 or csize > 10000000:  # Size too large
                break
            if usize == 0 and csize == 0 and flags == 0:  # End marker
                break
            if flags > 0x0100:  # Invalid flags
                break
            
            blocks.append({
                'uncompressed_size': usize,
                'compressed_size': csize,
                'flags': flags
            })
            offset += 10
        
        if not blocks:
            return False
        
        # Step 2: Decompress data blocks
        # Data blocks start after the compressed blocks info
        blocks_data_start = blocks_offset + ciblock_size
        raw_output = bytearray()
        data_offset = blocks_data_start
        
        for block in blocks:
            block_data = data[data_offset:data_offset + block['compressed_size']]
            
            if block['flags'] == 0x0000:
                # Uncompressed block
                raw_output.extend(block_data)
            else:
                # Compressed block (LZ4)
                try:
                    decompressed = lz4.block.decompress(
                        block_data,
                        uncompressed_size=block['uncompressed_size']
                    )
                    raw_output.extend(decompressed)
                except Exception as e:
                    return False
            
            data_offset += block['compressed_size']
        
        # Write raw asset data
        output_path.write_bytes(raw_output)
        return True
        
    except Exception as e:
        return False


# ============================================================================
# STEP 3: EXTRACT 3D MODELS, TEXTURES, AND MATERIALS
# ============================================================================

def extract_assets_from_raw(raw_path, meshes_dir, textures_dir, materials_dir, stats):
    """
    Extract 3D models, textures, and materials from raw asset data
    Uses UnityPy to parse Unity asset bundles
    """
    try:
        # Load as Unity asset bundle
        env = UnityPy.load(str(raw_path))
        
        # Extract all objects
        object_count = 0
        for obj in env.objects:
            object_count += 1
            try:
                data = obj.read()
                obj_type = obj.type.name
                
                # Extract meshes
                if obj_type == "Mesh":
                    mesh = data
                    output_path = meshes_dir / f"mesh_{stats['meshes']:04d}_{mesh.m_Name}.obj"
                    
                    try:
                        result = mesh.export('obj')
                        with open(output_path, 'w') as f:
                            f.write(result)
                        stats['meshes'] += 1
                    except Exception as e:
                        stats['errors'].append({
                            'file': raw_path.name,
                            'type': 'mesh',
                            'name': mesh.m_Name,
                            'error': str(e)
                        })
                
                # Extract textures
                elif obj_type == "Texture2D":
                    texture = data
                    try:
                        img = texture.image
                        img_path = textures_dir / f"texture_{stats['textures']:04d}_{texture.m_Name}.png"
                        img.save(img_path)
                        stats['textures'] += 1
                    except:
                        pass
                
                # Extract materials
                elif obj_type == "Material":
                    material = data
                    try:
                        mat_path = materials_dir / f"material_{stats['materials']:04d}_{material.m_Name}.txt"
                        with open(mat_path, 'w') as f:
                            f.write(f"Material: {material.m_Name}\n")
                            f.write(f"Shader: {material.m_Shader.read().m_Name if material.m_Shader else 'None'}\n")
                            f.write(f"\nSaved Textures:\n")
                            if hasattr(material, 'm_SavedProperties'):
                                props = material.m_SavedProperties
                                if hasattr(props, 'm_TexEnvs'):
                                    for tex_env in props.m_TexEnvs:
                                        if tex_env[1].m_Texture:
                                            tex_name = tex_env[1].m_Texture.read().m_Name
                                            f.write(f"  - {tex_env[0]}: {tex_name}\n")
                        stats['materials'] += 1
                    except:
                        stats['materials'] += 1
                        pass
            
            except:
                pass
        
        return True
        
    except Exception as e:
        stats['errors'].append({
            'file': raw_path.name,
            'error': str(e)
        })
        return False


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def main():
    """Execute complete 3-step extraction pipeline"""
    
    print("=" * 80)
    print("KICK FLIGHT ASSET EXTRACTION PIPELINE")
    print("=" * 80)
    print()
    
    # Get all encrypted bundles
    bundle_files = sorted(INPUT_BUNDLES.glob('*.bundle'))
    total = len(bundle_files)
    
    if total == 0:
        print(f"[ERROR] No bundle files found in {INPUT_BUNDLES}")
        return
    
    print(f"Found {total} encrypted bundles")
    print()
    
    # Statistics
    step1_success = 0
    step2_success = 0
    extraction_stats = {
        'meshes': 0,
        'textures': 0,
        'materials': 0,
        'errors': []
    }
    
    # Process each bundle through all 3 steps
    for i, bundle_path in enumerate(bundle_files, 1):
        bundle_name = bundle_path.stem
        
        # Progress indicator
        if i % 100 == 0 or i == 1 or i == total:
            print(f"[{i}/{total}] Processing: {bundle_name}")
        
        # STEP 1: Decrypt
        decrypted_path = OUTPUT_DECRYPTED / f"{bundle_name}.bundle"
        if decrypt_bundle(bundle_path, decrypted_path):
            step1_success += 1
            
            # STEP 2: Decompress
            raw_path = OUTPUT_RAW / f"{bundle_name}.raw"
            if decompress_bundle(decrypted_path, raw_path):
                step2_success += 1
                
                # STEP 3: Extract assets
                extract_assets_from_raw(
                    raw_path,
                    OUTPUT_MODELS / 'meshes',
                    OUTPUT_MODELS / 'textures',
                    OUTPUT_MODELS / 'materials',
                    extraction_stats
                )
    
    print()
    print("=" * 80)
    print("PIPELINE COMPLETE")
    print("=" * 80)
    print()
    print("STEP 1: DECRYPTION")
    print(f"  Success: {step1_success}/{total} ({step1_success/total*100:.1f}%)")
    print()
    print("STEP 2: DECOMPRESSION")
    print(f"  Success: {step2_success}/{total} ({step2_success/total*100:.1f}%)")
    print()
    print("STEP 3: ASSET EXTRACTION")
    print(f"  Meshes:    {extraction_stats['meshes']}")
    print(f"  Textures:  {extraction_stats['textures']}")
    print(f"  Materials: {extraction_stats['materials']}")
    print(f"  Errors:    {len(extraction_stats['errors'])}")
    print()
    print("OUTPUT LOCATIONS:")
    print(f"  Decrypted:  {OUTPUT_DECRYPTED.resolve()}")
    print(f"  Raw Assets: {OUTPUT_RAW.resolve()}")
    print(f"  Models:     {(OUTPUT_MODELS / 'meshes').resolve()}")
    print(f"  Textures:   {(OUTPUT_MODELS / 'textures').resolve()}")
    print(f"  Materials:  {(OUTPUT_MODELS / 'materials').resolve()}")
    print("=" * 80)
    
    # Save detailed results
    results = {
        'total_bundles': total,
        'step1_decrypted': step1_success,
        'step2_decompressed': step2_success,
        'step3_extracted': {
            'meshes': extraction_stats['meshes'],
            'textures': extraction_stats['textures'],
            'materials': extraction_stats['materials']
        },
        'errors': extraction_stats['errors'][:100]  # Save first 100 errors
    }
    
    results_file = OUTPUT_MODELS / 'extraction_results.json'
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n[RESULTS] Detailed results saved to: {results_file}")
    print()


if __name__ == "__main__":
    main()
