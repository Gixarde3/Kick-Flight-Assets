"""Kick-Flight preservation pipeline v3.

One command produces:

* repaired, complete UnityFS bundles (including CAB and .resS nodes);
* converted Unity assets and a complete object inventory;
* AnimationClip data as JSON plus exact serialized bytes;
* CRI USM streams, AWB/HCA entries and decoded WAV audio;
* untouched copies of every non-Unity/unknown source file;
* machine-readable manifests and an aggregate report.

The complete UnityFS files remain the authoritative content for a compatible
client. Converted files are research/editing conveniences, not replacements.
"""

from __future__ import annotations

import argparse
import base64
from collections import Counter
from enum import Enum
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Any, Iterable

import UnityPy

from reconstruct_unity_bundles import BundleRepairError, repair_bundle_bytes


DEFAULT_INPUT = Path("octo_sorted")
DEFAULT_OUTPUT = Path("PIPELINE_OUTPUT_V3")

IMAGE_TYPES = {"Texture2D", "Sprite", "Cubemap"}
JSON_TYPES = {
    "AnimationClip",
    "AnimatorController",
    "AnimatorOverrideController",
    "Avatar",
    "Material",
    "MonoBehaviour",
}
RAW_COMPANION_TYPES = {
    "AnimationClip",
    "AnimatorController",
    "AnimatorOverrideController",
    "Avatar",
    "MonoBehaviour",
}


def _safe_name(value: str | None, fallback: str = "unnamed", maximum: int = 100) -> str:
    value = (value or fallback).strip()
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or fallback
    return value[:maximum]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_default(value: Any) -> Any:
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"$base64": base64.b64encode(bytes(value)).decode("ascii")}
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "__dict__"):
        return vars(value)
    return str(value)


def _write_json(path: Path, value: Any, *, pretty: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2 if pretty else None,
            separators=None if pretty else (",", ":"),
            default=_json_default,
        ),
        encoding="utf-8",
    )


def _object_name(obj: Any) -> str:
    try:
        name = obj.peek_name()
        if name:
            return str(name)
    except Exception:
        pass
    try:
        return str(getattr(obj.read(), "m_Name", "") or "")
    except Exception:
        return ""


def _animation_duration(tree: dict[str, Any]) -> float | None:
    muscle = tree.get("m_MuscleClip") or {}
    for key in ("m_StopTime", "m_StartTime"):
        value = muscle.get(key)
        if key == "m_StopTime" and isinstance(value, (int, float)):
            return float(value)
    return None


def _text_asset_bytes(value: Any) -> bytes:
    """Undo UnityPy's surrogate-escape decoding without changing original bytes."""
    if isinstance(value, str):
        return value.encode("utf-8", errors="surrogateescape")
    return bytes(value)


class V3Pipeline:
    def __init__(self, input_root: Path, output_root: Path, *, limit: int | None = None):
        self.input_root = input_root
        self.output_root = output_root
        self.limit = limit
        self.bundle_output = output_root / "1_complete_unityfs"
        self.asset_output = output_root / "2_converted_unity_assets"
        self.media_output = output_root / "3_cri_media"
        self.preserved_output = output_root / "4_preserved_originals"
        self.manifest_output = output_root / "manifests"
        self.errors: list[dict[str, Any]] = []
        self.warnings: list[dict[str, Any]] = []
        self.object_types: Counter[str] = Counter()
        self.exported: Counter[str] = Counter()
        self.repair_types: Counter[str] = Counter()
        self.unity_manifest_path = self.manifest_output / "unity_objects.jsonl"
        self.animation_manifest: list[dict[str, Any]] = []
        self.media_manifest: list[dict[str, Any]] = []
        self.bundle_manifest: list[dict[str, Any]] = []

    def _record_error(self, stage: str, source: Path, error: Exception | str, **extra: Any) -> None:
        self.errors.append(
            {"stage": stage, "source": str(source), "error": str(error), **extra}
        )

    def _record_warning(self, stage: str, source: Path, warning: Exception | str, **extra: Any) -> None:
        self.warnings.append(
            {"stage": stage, "source": str(source), "warning": str(warning), **extra}
        )

    def _write_object_inventory(self, record: dict[str, Any]) -> None:
        self.unity_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with self.unity_manifest_path.open("a", encoding="utf-8") as output:
            output.write(json.dumps(record, ensure_ascii=False, default=_json_default) + "\n")

    def _export_unity_object(self, obj: Any, bundle_name: str) -> dict[str, Any]:
        object_type = obj.type.name
        name = _object_name(obj)
        safe = f"{obj.path_id}_{_safe_name(name)}"
        bundle_directory = _safe_name(Path(bundle_name).stem, maximum=150)
        assets_file_name = str(getattr(obj.assets_file, "name", "serialized") or "serialized")
        assets_file_directory = _safe_name(Path(assets_file_name).name, maximum=150)
        object_directory = Path(bundle_directory) / assets_file_directory
        record: dict[str, Any] = {
            "bundle": bundle_name,
            "assets_file": assets_file_name,
            "path_id": obj.path_id,
            "type": object_type,
            "name": name,
            "byte_size": obj.byte_size,
            "exports": [],
        }
        self.object_types[object_type] += 1

        try:
            if object_type in IMAGE_TYPES:
                data = obj.read()
                if getattr(data, "m_Width", 1) <= 0 or getattr(data, "m_Height", 1) <= 0:
                    destination = (
                        self.asset_output
                        / "unconverted_raw"
                        / object_type
                        / object_directory
                        / f"{safe}.bin"
                    )
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(obj.get_raw_data())
                    record["exports"].append(str(destination.relative_to(self.output_root)))
                    record["conversion_warning"] = "empty image dimensions"
                    self._record_warning(
                        "unity_export",
                        Path(bundle_name),
                        "empty image dimensions; serialized object preserved",
                        path_id=obj.path_id,
                        object_type=object_type,
                        name=name,
                    )
                    return record
                image = data.image
                destination = (
                    self.asset_output / "images" / object_type / object_directory / f"{safe}.png"
                )
                destination.parent.mkdir(parents=True, exist_ok=True)
                image.save(destination)
                image.close()
                record["exports"].append(str(destination.relative_to(self.output_root)))
                self.exported[f"{object_type}_png"] += 1

            elif object_type == "Mesh":
                data = obj.read()
                destination = self.asset_output / "meshes" / object_directory / f"{safe}.obj"
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(data.export(), encoding="utf-8")
                record["exports"].append(str(destination.relative_to(self.output_root)))
                self.exported["Mesh_obj"] += 1

            elif object_type in JSON_TYPES:
                raw_destination = None
                if object_type in RAW_COMPANION_TYPES:
                    raw_category = "animation_raw" if object_type == "AnimationClip" else "structured_raw"
                    raw_destination = (
                        self.asset_output
                        / raw_category
                        / ("" if object_type == "AnimationClip" else object_type)
                        / object_directory
                        / f"{safe}.bin"
                    )
                    raw_destination.parent.mkdir(parents=True, exist_ok=True)
                    raw_destination.write_bytes(obj.get_raw_data())
                    record["exports"].append(str(raw_destination.relative_to(self.output_root)))
                try:
                    tree = obj.read_typetree()
                except Exception as tree_error:
                    record["conversion_warning"] = str(tree_error)
                    self._record_warning(
                        "unity_typetree",
                        Path(bundle_name),
                        tree_error,
                        path_id=obj.path_id,
                        object_type=object_type,
                        name=name,
                    )
                    return record
                destination = (
                    self.asset_output
                    / "structured"
                    / object_type
                    / object_directory
                    / f"{safe}.json"
                )
                _write_json(destination, tree)
                record["exports"].append(str(destination.relative_to(self.output_root)))
                self.exported[f"{object_type}_json"] += 1
                if object_type == "AnimationClip":
                    animation_record = {
                        "bundle": bundle_name,
                        "assets_file": assets_file_name,
                        "path_id": obj.path_id,
                        "name": name,
                        "sample_rate": tree.get("m_SampleRate"),
                        "duration_seconds": _animation_duration(tree),
                        "legacy": tree.get("m_Legacy"),
                        "json": str(destination.relative_to(self.output_root)),
                        "serialized": str(raw_destination.relative_to(self.output_root)),
                    }
                    self.animation_manifest.append(animation_record)

            elif object_type == "TextAsset":
                data = obj.read()
                script = _text_asset_bytes(data.m_Script)
                destination = self.asset_output / "text_assets" / object_directory / f"{safe}.bin"
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(script)
                record["exports"].append(str(destination.relative_to(self.output_root)))
                self.exported["TextAsset_raw"] += 1

            elif object_type == "Shader":
                data = obj.read()
                destination = self.asset_output / "shaders" / object_directory / f"{safe}.shader"
                destination.parent.mkdir(parents=True, exist_ok=True)
                exported = data.export()
                if isinstance(exported, bytes):
                    destination.write_bytes(exported)
                else:
                    destination.write_text(str(exported), encoding="utf-8")
                record["exports"].append(str(destination.relative_to(self.output_root)))
                self.exported["Shader"] += 1

            elif object_type == "Font":
                data = obj.read()
                font_data = bytes(getattr(data, "m_FontData", b""))
                if font_data:
                    destination = self.asset_output / "fonts" / object_directory / f"{safe}.font"
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(font_data)
                    record["exports"].append(str(destination.relative_to(self.output_root)))
                    self.exported["Font_raw"] += 1
        except Exception as error:
            fallback = (
                self.asset_output
                / "unconverted_raw"
                / object_type
                / object_directory
                / f"{safe}.bin"
            )
            fallback.parent.mkdir(parents=True, exist_ok=True)
            fallback.write_bytes(obj.get_raw_data())
            record["exports"].append(str(fallback.relative_to(self.output_root)))
            self._record_warning(
                "unity_conversion",
                Path(bundle_name),
                error,
                path_id=obj.path_id,
                object_type=object_type,
                name=name,
            )
            record["conversion_warning"] = str(error)
        return record

    def process_unity(self) -> None:
        sources = sorted((self.input_root / "3_unity_bundles").glob("*.bundle"))
        if self.limit is not None:
            sources = sources[: self.limit]
        self.bundle_output.mkdir(parents=True, exist_ok=True)
        if self.unity_manifest_path.exists():
            self.unity_manifest_path.unlink()

        for index, source in enumerate(sources, 1):
            try:
                result = repair_bundle_bytes(source.read_bytes())
                destination = self.bundle_output / source.name
                destination.write_bytes(result.data)
                environment = UnityPy.load(str(destination))
                object_count = 0
                for obj in environment.objects:
                    object_count += 1
                    self._write_object_inventory(self._export_unity_object(obj, source.name))
                for repair in result.repairs:
                    self.repair_types[repair.split(".", 1)[0]] += 1
                self.bundle_manifest.append(
                    {
                        "source": source.name,
                        "output": str(destination.relative_to(self.output_root)),
                        "size": destination.stat().st_size,
                        "sha256": _sha256_file(destination),
                        "blocks": len(result.blocks),
                        "nodes": [node.path for node in result.nodes],
                        "objects": object_count,
                        "repairs": list(result.repairs),
                    }
                )
            except Exception as error:
                self._record_error("unity_bundle", source, error)
            if index == 1 or index % 100 == 0 or index == len(sources):
                print(
                    f"[Unity {index}/{len(sources)}] bundles={len(self.bundle_manifest)} "
                    f"objects={sum(self.object_types.values())} errors={len(self.errors)}",
                    flush=True,
                )

    def _preserve(self, source: Path, category: str) -> Path:
        destination = self.preserved_output / category / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return destination

    def process_cri(self) -> None:
        try:
            import cricodecs
        except ImportError as error:
            raise BundleRepairError("cricodecs is required for the v3 media stage") from error

        loose_sources = sorted((self.input_root / "2_cri_audio_video").glob("*"))
        archive_sources = sorted((self.input_root / "1_afs2_archives").glob("*"))
        if self.limit is not None:
            loose_sources = loose_sources[: self.limit]
            archive_sources = archive_sources[: self.limit]

        for index, source in enumerate(loose_sources, 1):
            preserved = self._preserve(source, "cri_loose")
            record: dict[str, Any] = {
                "source": source.name,
                "preserved": str(preserved.relative_to(self.output_root)),
                "sha256": _sha256_file(preserved),
            }
            try:
                media = cricodecs.load(source)
                detected = type(media).__module__.split(".")[-1]
                record["detected_format"] = detected
                record["container_filename"] = getattr(media, "container_filename", None)
                if detected == "usm":
                    destination = self.media_output / "usm_demux" / source.stem
                    destination.mkdir(parents=True, exist_ok=True)
                    media.extract(str(destination))
                    streams = []
                    for stream in media.streams:
                        streams.append(
                            {
                                "filename": stream.filename,
                                "stream_id": str(stream.stream_id),
                                "channel": stream.channel_no,
                                "audio_codec": str(stream.audio_codec) if stream.audio_codec else None,
                                "size": stream.filesize,
                            }
                        )
                    record["streams"] = streams
                    record["extracted_to"] = str(destination.relative_to(self.output_root))
                    self.exported["USM_demuxed"] += 1
            except Exception as error:
                self._record_error("cri_loose", source, error)
                record["error"] = str(error)
            self.media_manifest.append(record)
            if index == 1 or index % 25 == 0 or index == len(loose_sources):
                print(f"[CRI loose {index}/{len(loose_sources)}]", flush=True)

        for index, source in enumerate(archive_sources, 1):
            preserved = self._preserve(source, "afs2_awb")
            record = {
                "source": source.name,
                "preserved": str(preserved.relative_to(self.output_root)),
                "sha256": _sha256_file(preserved),
                "detected_format": "awb",
                "entries": [],
            }
            try:
                awb = cricodecs.awb.load(source)
                record["subkey"] = awb.subkey
                for entry_index in range(awb.file_count):
                    entry = awb.entries[entry_index]
                    encoded = awb.file_bytes(entry_index)
                    entry_dir = self.media_output / "awb_entries" / source.stem
                    entry_dir.mkdir(parents=True, exist_ok=True)
                    detected = cricodecs.load(encoded)
                    detected_format = type(detected).__module__.split(".")[-1]
                    encoded_path = entry_dir / f"{entry_index:04d}_wave_{entry.wave_id}.{detected_format}"
                    encoded_path.write_bytes(encoded)
                    entry_record: dict[str, Any] = {
                        "index": entry_index,
                        "wave_id": entry.wave_id,
                        "detected_format": detected_format,
                        "encoded": str(encoded_path.relative_to(self.output_root)),
                        "size": len(encoded),
                    }
                    if detected_format == "hca":
                        wav_path = entry_dir / f"{entry_index:04d}_wave_{entry.wave_id}.wav"
                        wav_path.write_bytes(detected.decode(subkey=awb.subkey))
                        entry_record["wav"] = str(wav_path.relative_to(self.output_root))
                        self.exported["HCA_wav"] += 1
                    record["entries"].append(entry_record)
            except Exception as error:
                self._record_error("afs2_awb", source, error)
                record["error"] = str(error)
            self.media_manifest.append(record)
            print(f"[AFS2 {index}/{len(archive_sources)}]", flush=True)

    def process_unknown(self) -> None:
        sources = sorted((self.input_root / "5_unknown").glob("*"))
        if self.limit is not None:
            sources = sources[: self.limit]
        for source in sources:
            preserved = self._preserve(source, "unknown")
            self.media_manifest.append(
                {
                    "source": source.name,
                    "detected_format": "unknown",
                    "preserved": str(preserved.relative_to(self.output_root)),
                    "size": preserved.stat().st_size,
                    "sha256": _sha256_file(preserved),
                }
            )

    def finish(self) -> dict[str, Any]:
        _write_json(self.manifest_output / "bundles.json", self.bundle_manifest, pretty=True)
        _write_json(self.manifest_output / "animations.json", self.animation_manifest, pretty=True)
        _write_json(self.manifest_output / "media.json", self.media_manifest, pretty=True)
        _write_json(self.manifest_output / "errors.json", self.errors, pretty=True)
        _write_json(self.manifest_output / "warnings.json", self.warnings, pretty=True)
        report = {
            "pipeline": "Kick-Flight asset pipeline v3",
            "complete_unity_bundles": len(self.bundle_manifest),
            "unity_objects": sum(self.object_types.values()),
            "unity_object_types": dict(self.object_types.most_common()),
            "animation_clips": len(self.animation_manifest),
            "media_records": len(self.media_manifest),
            "exports": dict(self.exported.most_common()),
            "repair_types": dict(self.repair_types.most_common()),
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "error_manifest": str((self.manifest_output / "errors.json").relative_to(self.output_root)),
            "warning_manifest": str((self.manifest_output / "warnings.json").relative_to(self.output_root)),
        }
        _write_json(self.output_root / "report_v3.json", report, pretty=True)
        return report

    def run(self) -> dict[str, Any]:
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.process_unity()
        self.process_cri()
        self.process_unknown()
        return self.finish()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, help="process the first N items in each category")
    args = parser.parse_args()
    pipeline = V3Pipeline(args.input, args.output, limit=args.limit)
    report = pipeline.run()
    print(json.dumps(report, indent=2))
    return 0 if report["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
