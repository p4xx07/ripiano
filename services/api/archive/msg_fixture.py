"""Build minimal Outlook .msg files (MS-CFB compound files) for tests.

Only what Ripiano reads is written: string and binary property streams, attachment storages.
Small streams use the mini stream, as the specification requires.
"""

import struct

SECTOR = 512
MINI = 64
MINI_CUTOFF = 4096
FREE, END, FAT_SECTOR, NOSTREAM = 0xFFFFFFFF, 0xFFFFFFFE, 0xFFFFFFFD, 0xFFFFFFFF


def _string(value):
    return value.encode("utf-16-le")


def build_msg(subject, sender_name, sender_email, body, attachments=(), headers=""):
    """Return .msg bytes. attachments: [(filename, bytes)]."""
    top = [
        ("__substg1.0_0037001F", _string(subject)),
        ("__substg1.0_0C1A001F", _string(sender_name)),
        ("__substg1.0_5D01001F", _string(sender_email)),
        ("__substg1.0_1000001F", _string(body)),
    ]
    if headers:
        top.append(("__substg1.0_007D001F", _string(headers)))
    storages = []
    for index, (name, data) in enumerate(attachments):
        storages.append((f"__attach_version1.0_#{index:08X}", [("__substg1.0_3707001F", _string(name)), ("__substg1.0_37010102", data)]))

    # Small streams (< 4096 bytes) live in the mini stream (64-byte mini sectors), large ones in regular sectors.
    sectors, chains, mini, mini_chains = [], {}, [], {}

    def place(key, data):
        if len(data) < MINI_CUTOFF:
            count = max(1, -(-len(data) // MINI))
            start = len(mini)
            padded = data + b"\0" * (count * MINI - len(data))
            mini.extend(padded[i:i + MINI] for i in range(0, len(padded), MINI))
            mini_chains[key] = (start, count, len(data))
            chains[key] = (start, 0, len(data))
            return
        count = -(-len(data) // SECTOR)
        start = len(sectors)
        padded = data + b"\0" * (count * SECTOR - len(data))
        sectors.extend(padded[i:i + SECTOR] for i in range(0, len(padded), SECTOR))
        chains[key] = (start, count, len(data))

    for name, data in top:
        place(("", name), data)
    for storage, streams in storages:
        for name, data in streams:
            place((storage, name), data)
    # The mini stream itself is a regular stream owned by the root entry.
    mini_bytes = b"".join(mini)
    mini_start = len(sectors) if mini_bytes else END
    mini_count = -(-len(mini_bytes) // SECTOR)
    if mini_bytes:
        padded = mini_bytes + b"\0" * (mini_count * SECTOR - len(mini_bytes))
        sectors.extend(padded[i:i + SECTOR] for i in range(0, len(padded), SECTOR))
    minifat = [FREE] * max(SECTOR // 4, -(-len(mini) // (SECTOR // 4)) * (SECTOR // 4))
    for start, count, _ in mini_chains.values():
        for offset in range(count):
            minifat[start + offset] = start + offset + 1 if offset + 1 < count else END
    minifat_bytes = struct.pack(f"<{len(minifat)}I", *minifat)
    minifat_start = len(sectors)
    minifat_count = len(minifat_bytes) // SECTOR
    sectors.extend(minifat_bytes[i:i + SECTOR] for i in range(0, len(minifat_bytes), SECTOR))

    # Directory entries: 0 root, then children linked as a right-sibling chain.
    entries = []

    def entry(name, kind, child=NOSTREAM, right=NOSTREAM, start=0, size=0):
        encoded = (name + "\0").encode("utf-16-le")
        raw = encoded.ljust(64, b"\0") + struct.pack("<HBB", len(encoded), kind, 1)
        raw += struct.pack("<III", NOSTREAM, right, child) + b"\0" * 16 + b"\0" * 4 + b"\0" * 16
        raw += struct.pack("<IQ", start, size)
        assert len(raw) == 128
        return raw

    plan = []  # (name, kind, start, size, children)
    for name, _ in top:
        start, _, size = chains[("", name)]
        plan.append((name, 2, start, size, []))
    for storage, streams in storages:
        kids = []
        for name, _ in streams:
            start, _, size = chains[(storage, name)]
            kids.append((name, 2, start, size, []))
        plan.append((storage, 1, 0, 0, kids))

    def emit(items):
        """Append entries for a sibling list; return the index of the first one."""
        indexes = []
        for name, kind, start, size, kids in items:
            indexes.append(len(entries))
            entries.append(None)
            child = emit(kids) if kids else NOSTREAM
            entries[indexes[-1]] = (name, kind, child, start, size)
        for position, index in enumerate(indexes):
            name, kind, child, start, size = entries[index]
            right = indexes[position + 1] if position + 1 < len(indexes) else NOSTREAM
            entries[index] = entry(name, kind, child, right, start, size)
        return indexes[0] if indexes else NOSTREAM

    entries.append(None)  # root placeholder
    first = emit(plan)
    entries[0] = entry("Root Entry", 5, first, NOSTREAM, mini_start, len(mini_bytes))
    directory = b"".join(entries)
    directory += b"\0" * ((-len(directory)) % SECTOR)
    dir_start = len(sectors)
    dir_count = len(directory) // SECTOR
    sectors.extend(directory[i:i + SECTOR] for i in range(0, len(directory), SECTOR))

    # FAT: chains for every stream and the directory, then the FAT sectors themselves.
    total = len(sectors)
    fat_count = 1
    while (total + fat_count) > fat_count * (SECTOR // 4):
        fat_count += 1
    fat = [FREE] * (fat_count * (SECTOR // 4))
    for start, count, _ in chains.values():
        for offset in range(count):  # count is 0 for mini-stream entries
            fat[start + offset] = start + offset + 1 if offset + 1 < count else END
    for offset in range(mini_count):
        fat[mini_start + offset] = mini_start + offset + 1 if offset + 1 < mini_count else END
    for offset in range(minifat_count):
        fat[minifat_start + offset] = minifat_start + offset + 1 if offset + 1 < minifat_count else END
    for offset in range(dir_count):
        fat[dir_start + offset] = dir_start + offset + 1 if offset + 1 < dir_count else END
    fat_start = total
    for offset in range(fat_count):
        fat[fat_start + offset] = FAT_SECTOR
    fat_bytes = struct.pack(f"<{len(fat)}I", *fat)

    header = bytes.fromhex("D0CF11E0A1B11AE1") + b"\0" * 16
    header += struct.pack("<HHHHH", 0x003E, 0x0003, 0xFFFE, 9, 6) + b"\0" * 6
    header += struct.pack("<IIIIIIIII", 0, fat_count, dir_start, 0, MINI_CUTOFF, minifat_start, minifat_count, END, 0)
    difat = [fat_start + offset for offset in range(fat_count)] + [FREE] * (109 - fat_count)
    header += struct.pack("<109I", *difat)
    assert len(header) == SECTOR
    return header + b"".join(sectors) + fat_bytes
