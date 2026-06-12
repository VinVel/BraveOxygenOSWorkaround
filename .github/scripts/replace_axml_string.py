#!/usr/bin/env python3
import argparse
import os
import shutil
import struct
import tempfile
import zipfile


UTF8_FLAG = 0x00000100
RES_STRING_POOL_TYPE = 0x0001
RES_XML_TYPE = 0x0003


def read_u16(data, offset):
    return struct.unpack_from("<H", data, offset)[0]


def read_u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def write_u32(buf, offset, value):
    struct.pack_into("<I", buf, offset, value)


def read_length8(data, offset):
    value = data[offset]
    offset += 1
    if value & 0x80:
        value = ((value & 0x7F) << 8) | data[offset]
        offset += 1
    return value, offset


def write_length8(value):
    if value > 0x7FFF:
        raise ValueError("UTF-8 string length is too large")
    if value > 0x7F:
        return bytes([0x80 | (value >> 8), value & 0xFF])
    return bytes([value])


def read_length16(data, offset):
    value = read_u16(data, offset)
    offset += 2
    if value & 0x8000:
        value = ((value & 0x7FFF) << 16) | read_u16(data, offset)
        offset += 2
    return value, offset


def write_length16(value):
    if value > 0x7FFFFFFF:
        raise ValueError("UTF-16 string length is too large")
    if value > 0x7FFF:
        return struct.pack("<HH", 0x8000 | (value >> 16), value & 0xFFFF)
    return struct.pack("<H", value)


def read_string(data, offset, utf8):
    if utf8:
        _, offset = read_length8(data, offset)
        byte_len, offset = read_length8(data, offset)
        raw = data[offset : offset + byte_len]
        return raw.decode("utf-8")

    char_len, offset = read_length16(data, offset)
    raw = data[offset : offset + char_len * 2]
    return raw.decode("utf-16le")


def encode_string(value, utf8):
    if utf8:
        raw = value.encode("utf-8")
        utf16_len = len(value.encode("utf-16le")) // 2
        return write_length8(utf16_len) + write_length8(len(raw)) + raw + b"\x00"

    raw = value.encode("utf-16le")
    return write_length16(len(raw) // 2) + raw + b"\x00\x00"


def replace_axml_string(manifest, old, new):
    data = bytearray(manifest)

    if read_u16(data, 0) != RES_XML_TYPE:
        raise ValueError("AndroidManifest.xml is not binary AXML")

    pool_start = 8
    if read_u16(data, pool_start) != RES_STRING_POOL_TYPE:
        raise ValueError("AXML string pool is not at the expected offset")

    header_size = read_u16(data, pool_start + 2)
    pool_size = read_u32(data, pool_start + 4)
    string_count = read_u32(data, pool_start + 8)
    style_count = read_u32(data, pool_start + 12)
    flags = read_u32(data, pool_start + 16)
    strings_start = read_u32(data, pool_start + 20)
    styles_start = read_u32(data, pool_start + 24)
    utf8 = bool(flags & UTF8_FLAG)

    offsets_start = pool_start + header_size
    strings_base = pool_start + strings_start
    strings_end = pool_start + (styles_start if style_count else pool_size)

    strings = []
    replacements = 0
    for i in range(string_count):
        string_offset = read_u32(data, offsets_start + i * 4)
        value = read_string(data, strings_base + string_offset, utf8)
        replacements += value.count(old)
        value = value.replace(old, new)
        strings.append(value)

    if replacements == 0:
        raise ValueError(f"String fragment not found in manifest string pool: {old}")

    new_offsets = bytearray()
    new_string_data = bytearray()
    for value in strings:
        new_offsets += struct.pack("<I", len(new_string_data))
        new_string_data += encode_string(value, utf8)

    while len(new_string_data) % 4:
        new_string_data += b"\x00"

    old_offsets_end = offsets_start + string_count * 4 + style_count * 4
    header_and_styles = data[pool_start:offsets_start] + new_offsets
    if style_count:
        header_and_styles += data[offsets_start + string_count * 4 : old_offsets_end]

    tail = data[strings_end : pool_start + pool_size]
    new_pool = bytearray(header_and_styles + new_string_data + tail)
    new_pool_size = len(new_pool)

    write_u32(new_pool, 4, new_pool_size)
    write_u32(new_pool, 20, strings_start)
    if style_count:
        write_u32(new_pool, 24, strings_start + len(new_string_data))

    new_data = bytearray(data[:pool_start] + new_pool + data[pool_start + pool_size :])
    write_u32(new_data, 4, len(new_data))
    return bytes(new_data)


def replace_manifest_in_apk(apk_path, old, new):
    fd, temp_path = tempfile.mkstemp(suffix=".apk")
    os.close(fd)

    try:
        with zipfile.ZipFile(apk_path, "r") as source, zipfile.ZipFile(temp_path, "w") as target:
            for entry in source.infolist():
                content = source.read(entry.filename)
                if entry.filename == "AndroidManifest.xml":
                    content = replace_axml_string(content, old, new)

                new_entry = zipfile.ZipInfo(entry.filename, date_time=entry.date_time)
                new_entry.compress_type = entry.compress_type
                new_entry.comment = entry.comment
                new_entry.extra = entry.extra
                new_entry.internal_attr = entry.internal_attr
                new_entry.external_attr = entry.external_attr
                target.writestr(new_entry, content)

        shutil.move(temp_path, apk_path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("apk")
    parser.add_argument("old")
    parser.add_argument("new")
    args = parser.parse_args()

    replace_manifest_in_apk(args.apk, args.old, args.new)


if __name__ == "__main__":
    main()
