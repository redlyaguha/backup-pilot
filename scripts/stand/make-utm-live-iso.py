#!/usr/bin/env python3
"""Create the pinned Astra 1.8.1 Live ISO variant used by the BP-02 UTM stand."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys

SOURCE_SHA256 = '8810c6b12dae2fb63a7c3dc0d2df28cd1eaa5c6a35f2524935949d5b54ca43e8'
OFFSETS = (9113447, 7006336871)
KERNEL_LINE = (b'linux /vmlinuz boot=live noapic console=ttyS0,115200n8 '
               b'systemd.debug_shell=ttyS0 systemd.unit=multi-user.target')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def create(source, output):
    source = source.resolve(strict=True)
    if output.exists() or output.is_symlink():
        raise ValueError('Output already exists; choose a new file.')
    if source.stat().st_size != 7013961728 or digest(source) != SOURCE_SHA256:
        raise ValueError('Input is not the pinned official Astra 1.8.1 ISO.')
    with source.open('rb') as stream:
        lines = []
        for offset in OFFSETS:
            stream.seek(offset)
            original = stream.readline()
            if not original.startswith(b'linux /vmlinuz ') or len(KERNEL_LINE) >= len(original):
                raise ValueError('Unexpected GRUB line at pinned offset.')
            lines.append(original)
    # APFS cloning avoids another full 6.5 GiB allocation on Apple Silicon hosts.
    if sys.platform == 'darwin':
        subprocess.run(['cp', '-c', str(source), str(output)], check=True)
    else:
        with source.open('rb') as src, output.open('xb') as dest:
            shutil.copyfileobj(src, dest, 1024 * 1024)
    with output.open('r+b') as stream:
        for offset, original in zip(OFFSETS, lines):
            stream.seek(offset)
            stream.write(KERNEL_LINE + b' ' * (len(original) - len(KERNEL_LINE) - 1) + b'\n')
    print('Original SHA256:', SOURCE_SHA256)
    print('Derived SHA256:', digest(output))
    print('Patched EFI GRUB offsets:', ', '.join(map(str, OFFSETS)))
    print('Live only: root debug console; detach this ISO before disk acceptance.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    try:
        create(args.source, args.output)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'Error: {exc}\n')
