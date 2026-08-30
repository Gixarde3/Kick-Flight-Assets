"""Rebuild Kick-Flight Octo files as complete, standard UnityFS bundles.

The original ``asset_extractor.py`` concatenates decompressed data blocks.  That
produces a raw byte stream, but drops the UnityFS node directory which associates
the serialized asset file with sidecar resources such as ``.resS``.  This tool
repairs the obfuscated metadata and writes a complete bundle instead.

It intentionally does not implement any game-server or network protocol.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import lz4.block


XOR_KEY = bytes((0x6F, 0x0F, 0xFA, 0x46, 0xD3, 0x28, 0x3A))
DEFAULT_INPUT = Path("octo_sorted/3_unity_bundles")
DEFAULT_OUTPUT = Path("PIPELINE_OUTPUT_V2/1_reconstructed_bundles")


class BundleRepairError(ValueError):
    """Raised when an Octo file cannot be repaired without guessing."""


@dataclass(frozen=True)
class Block:
    uncompressed_size: int
    compressed_size: int
    flags: int


@dataclass(frozen=True)
class Node:
    offset: int
    size: int
    flags: int
    path: str


@dataclass(frozen=True)
class RepairResult:
    data: bytes
    blocks: tuple[Block, ...]
    nodes: tuple[Node, ...]
    repairs: tuple[str, ...]


def _xor(data: bytes, key: bytes = XOR_KEY) -> bytes:
    return bytes(value ^ key[index % len(key)] for index, value in enumerate(data))


def _single_complement_candidates(raw: bytes) -> list[tuple[int, int | None]]:
    """Return the original big-endian integer and one-byte-complement variants."""
    candidates: list[tuple[int, int | None]] = [(int.from_bytes(raw, "big"), None)]
    for index in range(len(raw)):
        changed = bytearray(raw)
        changed[index] ^= 0xFF
        candidate = (int.from_bytes(changed, "big"), index)
        if candidate[0] not in {value for value, _ in candidates}:
            candidates.append(candidate)
    return candidates


def _repair_values_to_sum(
    raw_values: Sequence[bytes], target: int, label: str
) -> tuple[list[int], list[str]]:
    """Repair at most two complemented bytes so the integer values sum to target."""
    values = [int.from_bytes(value, "big") for value in raw_values]
    raw_sum = sum(values)
    if raw_sum == target:
        return values, []

    changes: list[tuple[int, int, int, int]] = []
    for item_index, raw in enumerate(raw_values):
        original = values[item_index]
        for candidate, byte_index in _single_complement_candidates(raw)[1:]:
            if candidate > 0:
                changes.append((item_index, candidate, candidate - original, byte_index))

    needed = target - raw_sum
    for item_index, candidate, delta, byte_index in changes:
        if delta == needed:
            repaired = values.copy()
            repaired[item_index] = candidate
            return repaired, [f"{label}[{item_index}].byte[{byte_index}]"]

    by_delta: dict[int, tuple[int, int, int]] = {}
    for item_index, candidate, delta, byte_index in changes:
        other = by_delta.get(needed - delta)
        if other is not None and other[0] != item_index:
            repaired = values.copy()
            repaired[item_index] = candidate
            repaired[other[0]] = other[1]
            return repaired, [
                f"{label}[{item_index}].byte[{byte_index}]",
                f"{label}[{other[0]}].byte[{other[2]}]",
            ]
        by_delta.setdefault(delta, (item_index, candidate, byte_index))

    raise BundleRepairError(
        f"cannot repair {label} sum: raw={raw_sum}, expected={target}"
    )


def _repair_flag(raw: bytes, allowed: set[int], label: str) -> tuple[int, str | None]:
    for candidate, byte_index in _single_complement_candidates(raw):
        if candidate in allowed:
            repair = None if byte_index is None else f"{label}.byte[{byte_index}]"
            return candidate, repair
    raise BundleRepairError(f"invalid {label}: 0x{int.from_bytes(raw, 'big'):x}")


def _parse_nodes_exact(
    blocks_info: bytes, offset: int, count: int
) -> tuple[list[tuple[bytes, bytes, bytes, str]], int] | None:
    nodes: list[tuple[bytes, bytes, bytes, str]] = []
    cursor = offset
    try:
        for _ in range(count):
            if cursor + 20 > len(blocks_info):
                return None
            raw_offset = blocks_info[cursor : cursor + 8]
            raw_size = blocks_info[cursor + 8 : cursor + 16]
            raw_flags = blocks_info[cursor + 16 : cursor + 20]
            cursor += 20
            end = blocks_info.index(0, cursor)
            path = blocks_info[cursor:end].decode("utf-8")
            cursor = end + 1
            nodes.append((raw_offset, raw_size, raw_flags, path))
    except (ValueError, UnicodeDecodeError):
        return None
    return (nodes, cursor) if cursor == len(blocks_info) else None


def _repair_node_layout(
    raw_nodes: Sequence[tuple[bytes, bytes, bytes, str]], total_size: int
) -> tuple[list[Node], list[str]]:
    """Find the unique contiguous node layout ending at total_size."""
    solutions: list[list[tuple[int, int, int | None, int | None]]] = []

    def visit(index: int, expected_offset: int, selected: list[tuple[int, int, int | None, int | None]]) -> None:
        if index == len(raw_nodes):
            if expected_offset == total_size:
                solutions.append(selected.copy())
            return

        raw_offset, raw_size, _, _ = raw_nodes[index]
        matching_offsets = [
            (value, byte_index)
            for value, byte_index in _single_complement_candidates(raw_offset)
            if value == expected_offset
        ]
        for offset_value, offset_byte in matching_offsets:
            for size_value, size_byte in _single_complement_candidates(raw_size):
                if size_value < 0 or offset_value + size_value > total_size:
                    continue
                selected.append((offset_value, size_value, offset_byte, size_byte))
                visit(index + 1, offset_value + size_value, selected)
                selected.pop()

    visit(0, 0, [])
    if not solutions:
        raise BundleRepairError(
            f"node layout has no solution for total size {total_size}"
        )

    # Complemented bytes are exceptional.  Prefer the valid layout requiring the
    # fewest repairs; alternate multi-complement layouts can otherwise be created
    # mathematically even when every original node field was already correct.
    repair_counts = [
        sum(offset_byte is not None for _, _, offset_byte, _ in solution)
        + sum(size_byte is not None for _, _, _, size_byte in solution)
        for solution in solutions
    ]
    minimum_repairs = min(repair_counts)
    best = [
        solution
        for solution, repair_count in zip(solutions, repair_counts)
        if repair_count == minimum_repairs
    ]
    if len(best) != 1:
        raise BundleRepairError(
            f"node layout has {len(best)} equally minimal solutions for total size {total_size}"
        )

    repaired_nodes: list[Node] = []
    repairs: list[str] = []
    layout = best[0]
    for index, ((_, _, raw_flags, path), (offset, size, offset_byte, size_byte)) in enumerate(
        zip(raw_nodes, layout)
    ):
        flags, flag_repair = _repair_flag(raw_flags, {0, 1, 2, 4}, f"node_flags[{index}]")
        if offset_byte is not None:
            repairs.append(f"node_offset[{index}].byte[{offset_byte}]")
        if size_byte is not None:
            repairs.append(f"node_size[{index}].byte[{size_byte}]")
        if flag_repair:
            repairs.append(flag_repair)
        repaired_nodes.append(Node(offset, size, flags, path))
    return repaired_nodes, repairs


def _decode_blocks_info(data: bytes, compressed_size: int, uncompressed_size: int) -> tuple[bytes, list[str]]:
    compressed = bytearray(data[54 : 54 + compressed_size])
    try:
        return (
            lz4.block.decompress(bytes(compressed), uncompressed_size=uncompressed_size),
            [],
        )
    except lz4.block.LZ4BlockError as first_error:
        if len(compressed) <= 5:
            raise BundleRepairError(f"blocks-info LZ4 failed: {first_error}") from first_error
        compressed[5] ^= 0xFF
        try:
            return (
                lz4.block.decompress(bytes(compressed), uncompressed_size=uncompressed_size),
                ["compressed_blocks_info.byte[5]"],
            )
        except lz4.block.LZ4BlockError as second_error:
            raise BundleRepairError(
                f"blocks-info LZ4 failed before and after byte[5] repair: {second_error}"
            ) from second_error


def _candidate_block_counts(raw_count: bytes, blocks_info_size: int) -> Iterable[tuple[int, int | None]]:
    maximum = max(0, (blocks_info_size - 24) // 10)
    for count, byte_index in _single_complement_candidates(raw_count):
        if 0 < count <= maximum:
            yield count, byte_index


def repair_bundle_bytes(data: bytes) -> RepairResult:
    """Repair one custom Kick-Flight Octo file and return a standard UnityFS file."""
    if len(data) < 55:
        raise BundleRepairError("file is too short")
    if _xor(data[:7]) != b"UnityFS":
        raise BundleRepairError("XOR-decrypted signature is not UnityFS")

    format_version = struct.unpack(">I", data[12:16])[0]
    if format_version != 6:
        raise BundleRepairError(f"unsupported UnityFS format {format_version}")
    compressed_info_size = struct.unpack(">I", data[42:46])[0]
    uncompressed_info_size = struct.unpack(">I", data[46:50])[0]
    payload_offset = 54 + compressed_info_size
    if payload_offset > len(data):
        raise BundleRepairError("blocks-info extends beyond the file")

    blocks_info, initial_repairs = _decode_blocks_info(
        data, compressed_info_size, uncompressed_info_size
    )
    if len(blocks_info) < 24:
        raise BundleRepairError("decompressed blocks-info is too short")
    payload = data[payload_offset:]

    candidates: list[tuple[list[Block], list[Node], list[str], bytes]] = []
    for block_count, count_byte in _candidate_block_counts(blocks_info[16:20], len(blocks_info)):
        node_count_offset = 20 + block_count * 10
        if node_count_offset + 4 > len(blocks_info):
            continue

        raw_blocks = [
            (
                blocks_info[20 + i * 10 : 24 + i * 10],
                blocks_info[24 + i * 10 : 28 + i * 10],
                blocks_info[28 + i * 10 : 30 + i * 10],
            )
            for i in range(block_count)
        ]

        for node_count, node_count_byte in _single_complement_candidates(
            blocks_info[node_count_offset : node_count_offset + 4]
        ):
            if node_count <= 0:
                continue
            parsed = _parse_nodes_exact(blocks_info, node_count_offset + 4, node_count)
            if parsed is None:
                continue
            raw_nodes, _ = parsed
            try:
                compressed_sizes, size_repairs = _repair_values_to_sum(
                    [block[1] for block in raw_blocks], len(payload), "compressed_size"
                )
                uncompressed_sizes = [int.from_bytes(block[0], "big") for block in raw_blocks]
                total_uncompressed = sum(uncompressed_sizes)
                nodes, node_repairs = _repair_node_layout(raw_nodes, total_uncompressed)
                blocks: list[Block] = []
                flag_repairs: list[str] = []
                for index, (raw_block, compressed_size) in enumerate(
                    zip(raw_blocks, compressed_sizes)
                ):
                    flags, flag_repair = _repair_flag(
                        raw_block[2], {0, 1, 2, 3}, f"block_flags[{index}]"
                    )
                    if flag_repair:
                        flag_repairs.append(flag_repair)
                    blocks.append(Block(uncompressed_sizes[index], compressed_size, flags))
            except BundleRepairError:
                continue

            repairs = list(initial_repairs)
            if count_byte is not None:
                repairs.append(f"block_count.byte[{count_byte}]")
            if node_count_byte is not None:
                repairs.append(f"node_count.byte[{node_count_byte}]")
            repairs.extend(size_repairs)
            repairs.extend(flag_repairs)
            repairs.extend(node_repairs)

            rebuilt_info = bytearray(blocks_info[:16])
            rebuilt_info.extend(struct.pack(">I", len(blocks)))
            for block in blocks:
                rebuilt_info.extend(
                    struct.pack(">IIH", block.uncompressed_size, block.compressed_size, block.flags)
                )
            rebuilt_info.extend(struct.pack(">I", len(nodes)))
            for node in nodes:
                rebuilt_info.extend(struct.pack(">QQI", node.offset, node.size, node.flags))
                rebuilt_info.extend(node.path.encode("utf-8") + b"\0")
            candidates.append((blocks, nodes, repairs, bytes(rebuilt_info)))

    if len(candidates) != 1:
        raise BundleRepairError(f"expected one metadata repair, found {len(candidates)}")

    blocks, nodes, repairs, rebuilt_info = candidates[0]
    compressed_info = lz4.block.compress(
        rebuilt_info, mode="high_compression", compression=9, store_size=False
    )

    # A normal format-6 UnityFS header is 50 bytes: the signature is a C string
    # and therefore includes its NUL terminator.  The custom source replaces it
    # with seven encrypted bytes plus five junk bytes and stores flags at [50:54].
    header_prefix = b"UnityFS\0" + data[12:34]
    total_size = 50 + len(compressed_info) + len(payload)
    header = (
        header_prefix
        + struct.pack(">QII", total_size, len(compressed_info), len(rebuilt_info))
        + struct.pack(">I", 0x00000003)  # LZ4 blocks-info, stored directly after header
    )
    if len(header) != 50:
        raise AssertionError(f"internal error: header is {len(header)} bytes")
    rebuilt = header + compressed_info + payload
    if len(rebuilt) != total_size:
        raise AssertionError("internal error: rebuilt file size mismatch")
    return RepairResult(rebuilt, tuple(blocks), tuple(nodes), tuple(repairs))


def _verify_with_unitypy(path: Path) -> int:
    try:
        import UnityPy
    except ImportError as error:
        raise BundleRepairError("UnityPy is required for --verify") from error
    environment = UnityPy.load(str(path))
    return sum(1 for _ in environment.objects)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rebuild_all(
    input_directory: Path,
    output_directory: Path,
    *,
    verify: bool = True,
    limit: int | None = None,
) -> dict:
    files = sorted(input_directory.glob("*.bundle"))
    if limit is not None:
        files = files[:limit]
    if not files:
        raise BundleRepairError(f"no .bundle files found in {input_directory}")
    output_directory.mkdir(parents=True, exist_ok=True)

    report: dict = {
        "input_directory": str(input_directory),
        "output_directory": str(output_directory),
        "requested": len(files),
        "rebuilt": 0,
        "verified": 0,
        "objects": 0,
        "files": [],
        "errors": [],
    }

    for index, source in enumerate(files, 1):
        destination = output_directory / source.name
        try:
            result = repair_bundle_bytes(source.read_bytes())
            temporary = destination.with_suffix(destination.suffix + ".tmp")
            temporary.write_bytes(result.data)
            temporary.replace(destination)
            object_count = _verify_with_unitypy(destination) if verify else None
            report["rebuilt"] += 1
            if object_count is not None:
                report["verified"] += 1
                report["objects"] += object_count
            report["files"].append(
                {
                    "source": source.name,
                    "output": destination.name,
                    "size": len(result.data),
                    "sha256": _sha256(result.data),
                    "blocks": len(result.blocks),
                    "nodes": [node.path for node in result.nodes],
                    "repairs": list(result.repairs),
                    "objects": object_count,
                }
            )
        except Exception as error:  # keep the batch running and report the exact file
            report["errors"].append({"source": source.name, "error": str(error)})
        if index == 1 or index % 100 == 0 or index == len(files):
            print(
                f"[{index}/{len(files)}] rebuilt={report['rebuilt']} "
                f"verified={report['verified']} errors={len(report['errors'])}",
                flush=True,
            )

    report_path = output_directory.parent / "bundle_rebuild_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-verify", action="store_true", help="skip loading outputs with UnityPy")
    parser.add_argument("--limit", type=int, help="process only the first N files (for testing)")
    arguments = parser.parse_args()

    report = rebuild_all(
        arguments.input,
        arguments.output,
        verify=not arguments.no_verify,
        limit=arguments.limit,
    )
    print(
        f"Complete: {report['rebuilt']}/{report['requested']} rebuilt, "
        f"{report['verified']} verified, {len(report['errors'])} errors"
    )
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
