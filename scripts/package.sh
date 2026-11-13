#!/bin/sh
set -eu

# Build backup-pilot_<version>_amd64.deb from the current tree.
# No debhelper: source tree -> staging -> dpkg-deb --build.

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

VERSION=$(python3 - <<'PY'
import sys
sys.path.insert(0, 'src')
from backup_pilot import __version__
print(__version__)
PY
)

CONTROL_VERSION=$(sed -n 's/^Version: *//p' "$ROOT/debian/control")
if [ "$VERSION" != "$CONTROL_VERSION" ]; then
    echo "package: version mismatch: code=$VERSION control=$CONTROL_VERSION" >&2
    exit 1
fi

PACKAGE="backup-pilot"
DEB="${PACKAGE}_${VERSION}_amd64.deb"
STAGE=$(mktemp -d)
chmod 755 "$STAGE"
cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT INT TERM

# application code -> /usr/lib/backup-pilot
install -d -m 755 "$STAGE/usr/lib/backup-pilot"
cp -R "$ROOT/src/backup_pilot" "$STAGE/usr/lib/backup-pilot/"
rm -rf "$STAGE/usr/lib/backup-pilot/backup_pilot/__pycache__"

# launcher -> /usr/bin
install -d -m 755 "$STAGE/usr/bin"
install -m 755 "$ROOT/debian/backup-pilot" "$STAGE/usr/bin/backup-pilot"

# systemd unit templates -> /lib/systemd/system
if [ -d "$ROOT/systemd" ]; then
    install -d -m 755 "$STAGE/lib/systemd/system"
    for unit in "$ROOT"/systemd/*; do
        [ -f "$unit" ] || continue
        install -m 644 "$unit" "$STAGE/lib/systemd/system/"
    done
fi

# configuration and data directories
install -d -m 755 "$STAGE/etc/backup-pilot/profiles.d"
install -d -m 755 "$STAGE/var/lib/backup-pilot"

# Debian metadata
install -d -m 755 "$STAGE/DEBIAN"
install -m 644 "$ROOT/debian/control" "$STAGE/DEBIAN/control"
install -m 755 "$ROOT/debian/postinst" "$STAGE/DEBIAN/postinst"

# build
install -d -m 755 "$ROOT/dist"
dpkg-deb --build --root-owner-group "$STAGE" "$ROOT/dist/$DEB"
echo "built $ROOT/dist/$DEB"
