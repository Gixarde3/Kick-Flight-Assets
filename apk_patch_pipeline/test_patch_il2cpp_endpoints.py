from __future__ import annotations

import struct
import unittest

from patch_il2cpp_endpoints import (
    METADATA_VERSION,
    ORIGINAL_LITERALS,
    SANITY,
    normalize_base_url,
    patch_metadata_bytes,
    patch_native_bytes,
)


def build_fake_metadata() -> tuple[bytes, int]:
    originals = list(ORIGINAL_LITERALS)
    literal_blob = bytearray()
    records: list[tuple[int, int]] = []
    for value in originals:
        encoded = value.encode("utf-8")
        records.append((len(encoded), len(literal_blob)))
        literal_blob.extend(encoded)

    literal_offset = 32
    literal_count = len(records) * 8
    literal_data_offset = literal_offset + literal_count
    literal_data_count = len(literal_blob)
    next_section_offset = literal_data_offset + literal_data_count

    header = bytearray(literal_offset)
    struct.pack_into("<II", header, 0, SANITY, METADATA_VERSION)
    struct.pack_into("<IIII", header, 8, literal_offset, literal_count, literal_data_offset, literal_data_count)
    struct.pack_into("<II", header, 24, next_section_offset, 4)
    table = b"".join(struct.pack("<II", *record) for record in records)
    return bytes(header + table + literal_blob + b"TAIL"), next_section_offset


class EndpointPatchTests(unittest.TestCase):
    def test_normalizes_http_url(self) -> None:
        self.assertEqual(
            normalize_base_url("http://192.168.1.50:18080/"),
            ("http://192.168.1.50:18080", "192.168.1.50:18080"),
        )

    def test_rejects_https_and_credentials(self) -> None:
        with self.assertRaisesRegex(ValueError, "http://"):
            normalize_base_url("https://localhost:18080")
        with self.assertRaisesRegex(ValueError, "only scheme"):
            normalize_base_url("http://user:pass@localhost:18080")

    def test_patches_metadata_and_shifts_later_sections(self) -> None:
        source, old_next_section = build_fake_metadata()
        output, report = patch_metadata_bytes(source, "http://10.0.2.2:18080", "10.0.2.2:18080")
        new_literal_data_count = struct.unpack_from("<I", output, 20)[0]
        old_literal_data_count = struct.unpack_from("<I", source, 20)[0]
        delta = new_literal_data_count - old_literal_data_count
        shifted_next_section = struct.unpack_from("<I", output, 24)[0]

        self.assertEqual(shifted_next_section, old_next_section + delta)
        self.assertEqual(len(report), 3)
        self.assertEqual(output[-4:], b"TAIL")
        self.assertGreater(len(output), len(source))

    def test_native_patch_requires_exact_guard(self) -> None:
        patch = {"offset": 2, "expected": b"ABCD", "replacement": b"WXYZ"}
        output, report = patch_native_bytes(b"00ABCD99", "test", patch)
        self.assertEqual(output, b"00WXYZ99")
        self.assertEqual(report["offset"], "0x2")
        with self.assertRaisesRegex(ValueError, "guard failed"):
            patch_native_bytes(b"00ABCE99", "test", patch)

    def test_rejects_wrong_metadata_version_without_changes(self) -> None:
        source, _ = build_fake_metadata()
        altered = bytearray(source)
        struct.pack_into("<I", altered, 4, 99)
        with self.assertRaisesRegex(ValueError, "unsupported"):
            patch_metadata_bytes(bytes(altered), "http://localhost:18080", "localhost:18080")


if __name__ == "__main__":
    unittest.main()
