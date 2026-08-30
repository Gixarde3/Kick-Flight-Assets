from pathlib import Path

from asset_extractor import V3Pipeline, _safe_name, _text_asset_bytes


def test_safe_name_removes_paths_and_metacharacters():
    assert _safe_name("../character/a:*? texture") == "character_a_texture"


def test_text_asset_surrogates_round_trip_to_original_bytes():
    original = b"config:\x80\xff\x00"
    decoded = original.decode("utf-8", errors="surrogateescape")
    assert _text_asset_bytes(decoded) == original


def test_v3_smoke_run(tmp_path: Path):
    report = V3Pipeline(Path("octo_sorted"), tmp_path / "v3", limit=1).run()

    assert report["complete_unity_bundles"] == 1
    assert report["unity_objects"] > 0
    assert report["exports"]["USM_demuxed"] == 1
    assert report["exports"]["HCA_wav"] == 1
    assert (tmp_path / "v3" / "report_v3.json").is_file()
    assert (tmp_path / "v3" / "manifests" / "unity_objects.jsonl").is_file()
