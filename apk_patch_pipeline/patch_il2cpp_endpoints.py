"""Patch Kick-Flight 2.11.0 IL2CPP endpoints for a direct private server.

The patch is intentionally version-locked. It validates the source metadata,
all target literals, and both native instruction guards before writing files.
It never contacts a remote service and only operates on an apktool work copy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


SANITY = 0xFAB11BAF
METADATA_VERSION = 24
ORIGINAL_LITERALS = {
    "https://colorful-api-octo-sb.grenge.jp": "base_url",
    "https://kickflight-resource-api.grenge.jp": "base_url",
    "kickflight-api.grenge.jp/": "authority",
}
NATIVE_PATCHES = {
    "arm64-v8a": {
        "offset": 0x31B5024,
        "expected": bytes.fromhex("28118a9a"),
        "replacement": bytes.fromhex("e8030aaa"),  # mov x8, x10: keep HTTP
    },
    "armeabi-v7a": {
        "offset": 0x2AC1798,
        "expected": bytes.fromhex("02309f17"),
        "replacement": bytes.fromhex("0000a0e1"),  # mov r0, r0: skip HTTPS override
    },
}


def sha256_bytes(data: bytes | bytearray) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def normalize_base_url(value: str) -> tuple[str, str]:
    parsed = urlsplit(value.strip())
    if parsed.scheme.lower() != "http":
        raise ValueError("serverBaseUrl must use http:// for certificate-free LAN access")
    if (
        not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("serverBaseUrl must contain only scheme, host, and optional port")
    authority = parsed.netloc
    return f"http://{authority}", authority


def patch_metadata_bytes(source: bytes, base_url: str, authority: str) -> tuple[bytes, list[dict[str, Any]]]:
    data = bytearray(source)
    if len(data) < 24:
        raise ValueError("IL2CPP metadata is too small")
    sanity, version = struct.unpack_from("<II", data, 0)
    if sanity != SANITY or version != METADATA_VERSION:
        raise ValueError(f"unsupported IL2CPP metadata header: sanity=0x{sanity:x}, version={version}")

    literal_offset, literal_count, literal_data_offset, literal_data_count = struct.unpack_from("<IIII", data, 8)
    if literal_count % 8:
        raise ValueError("invalid IL2CPP string literal table size")
    literal_table_end = literal_offset + literal_count
    literal_data_end = literal_data_offset + literal_data_count
    if not (24 <= literal_offset <= literal_table_end <= len(data)):
        raise ValueError("string literal table is outside the metadata file")
    if not (literal_table_end <= literal_data_offset <= literal_data_end <= len(data)):
        raise ValueError("string literal data is outside the metadata file")

    targets: dict[str, tuple[int, int]] = {}
    for index in range(literal_count // 8):
        length, data_index = struct.unpack_from("<II", data, literal_offset + index * 8)
        start = literal_data_offset + data_index
        end = start + length
        if start < literal_data_offset or end > literal_data_end:
            raise ValueError(f"literal {index} points outside the literal-data section")
        raw = bytes(data[start:end])
        try:
            value = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if value in ORIGINAL_LITERALS:
            if value in targets:
                raise ValueError(f"duplicate target literal: {value}")
            targets[value] = (index, data_index)

    missing = sorted(set(ORIGINAL_LITERALS) - set(targets))
    if missing:
        raise ValueError(f"missing expected endpoint literals: {missing}")

    replacement_blob = bytearray()
    report: list[dict[str, Any]] = []
    for original, kind in ORIGINAL_LITERALS.items():
        replacement = base_url if kind == "base_url" else f"{authority}/"
        encoded = replacement.encode("utf-8")
        index, original_data_index = targets[original]
        new_data_index = literal_data_count + len(replacement_blob)
        struct.pack_into("<II", data, literal_offset + index * 8, len(encoded), new_data_index)
        replacement_blob.extend(encoded)
        report.append(
            {
                "literalIndex": index,
                "originalDataIndex": original_data_index,
                "newDataIndex": new_data_index,
                "from": original,
                "to": replacement,
            }
        )

    while len(replacement_blob) % 4:
        replacement_blob.append(0)

    insertion_offset = literal_data_end
    delta = len(replacement_blob)
    data[insertion_offset:insertion_offset] = replacement_blob

    # Header entries are offset/count pairs. Shift every later section whose
    # absolute offset points at or beyond the insertion point.
    for pair_offset in range(8, literal_offset, 8):
        section_offset = struct.unpack_from("<I", data, pair_offset)[0]
        if section_offset >= insertion_offset:
            struct.pack_into("<I", data, pair_offset, section_offset + delta)
    struct.pack_into("<I", data, 20, literal_data_count + delta)
    return bytes(data), report


def patch_native_bytes(source: bytes, abi: str, patch: dict[str, Any] | None = None) -> tuple[bytes, dict[str, Any]]:
    selected = patch or NATIVE_PATCHES[abi]
    offset = int(selected["offset"])
    expected = bytes(selected["expected"])
    replacement = bytes(selected["replacement"])
    if len(expected) != len(replacement):
        raise ValueError(f"{abi} patch changes instruction length")
    if offset < 0 or offset + len(expected) > len(source):
        raise ValueError(f"{abi} patch offset 0x{offset:x} is outside the native library")
    actual = source[offset : offset + len(expected)]
    if actual != expected:
        raise ValueError(
            f"{abi} native patch guard failed at 0x{offset:x}: "
            f"expected {expected.hex()}, found {actual.hex()}"
        )
    data = bytearray(source)
    data[offset : offset + len(replacement)] = replacement
    return bytes(data), {
        "abi": abi,
        "offset": f"0x{offset:x}",
        "from": expected.hex(),
        "to": replacement.hex(),
    }


def build_patch(metadata_path: Path, native_paths: dict[str, Path], base_url: str) -> tuple[dict[Path, bytes], dict[str, Any]]:
    normalized_url, authority = normalize_base_url(base_url)
    metadata_source = metadata_path.read_bytes()
    native_sources = {abi: path.read_bytes() for abi, path in native_paths.items()}

    # Validate and construct every output before touching the work-copy files.
    metadata_output, metadata_report = patch_metadata_bytes(metadata_source, normalized_url, authority)
    native_outputs: dict[str, bytes] = {}
    native_report: list[dict[str, Any]] = []
    for abi, source in native_sources.items():
        output, item = patch_native_bytes(source, abi)
        native_outputs[abi] = output
        item["beforeSha256"] = sha256_bytes(source)
        item["afterSha256"] = sha256_bytes(output)
        native_report.append(item)

    outputs = {metadata_path: metadata_output}
    outputs.update({native_paths[abi]: data for abi, data in native_outputs.items()})
    report = {
        "schemaVersion": 1,
        "baseUrl": normalized_url,
        "authority": authority,
        "metadata": {
            "beforeSha256": sha256_bytes(metadata_source),
            "afterSha256": sha256_bytes(metadata_output),
            "literals": metadata_report,
        },
        "native": native_report,
    }
    return outputs, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--arm64", required=True, type=Path)
    parser.add_argument("--armv7", required=True, type=Path)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    paths = {
        "arm64-v8a": args.arm64,
        "armeabi-v7a": args.armv7,
    }
    outputs, report = build_patch(args.metadata, paths, args.base_url)
    for path, data in outputs.items():
        path.write_bytes(data)

    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
