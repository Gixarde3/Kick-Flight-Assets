from pathlib import Path

import UnityPy

from reconstruct_unity_bundles import repair_bundle_bytes


INPUT = Path("octo_sorted/3_unity_bundles")


def test_rebuild_preserves_complete_node_directory():
    source = next(INPUT.glob("*.bundle"))
    result = repair_bundle_bytes(source.read_bytes())

    assert result.data.startswith(b"UnityFS")
    assert len(result.nodes) >= 1
    assert sum(node.size for node in result.nodes) == sum(
        block.uncompressed_size for block in result.blocks
    )
    assert sum(block.compressed_size for block in result.blocks) > 0
    assert sum(1 for _ in UnityPy.load(result.data).objects) > 0


def test_rebuild_handles_complemented_compressed_size():
    source = INPUT / "4171434833524D_dd63004369a4956f3bb98a6d10218fd4.bundle"
    result = repair_bundle_bytes(source.read_bytes())

    assert "compressed_size[0].byte[1]" in result.repairs
    assert sum(block.compressed_size for block in result.blocks) == 83379
    assert any(node.path.endswith(".resS") for node in result.nodes)


def test_rebuild_handles_complemented_high_count_byte():
    source = INPUT / "41334B61587037_93e6ac410f852bf8271b5e1323537a37.bundle"
    result = repair_bundle_bytes(source.read_bytes())

    assert len(result.blocks) == 650
    assert "block_count.byte[2]" in result.repairs
