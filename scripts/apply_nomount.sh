#!/usr/bin/env bash
# Apply NoMount Kernel Driver (VFS Path Redirection via NoMount)
# Upstream: https://github.com/maxsteeel/nomount
# Usage: bash scripts/apply_nomount.sh <android_version> <kernel_version> <kernel_root>

set -eo pipefail

ANDROID_VER="${1:-android14}"
KERNEL_VER="${2:-6.1}"
KERNEL_ROOT="${3:-$GITHUB_WORKSPACE}"

echo "========================================"
echo "       NoMount Kernel Integration       "
echo "========================================"
echo "Android Version : $ANDROID_VER"
echo "Kernel Version  : $KERNEL_VER"
echo "Kernel Root     : $KERNEL_ROOT"
echo "Upstream Repo   : https://github.com/maxsteeel/nomount"
echo "========================================"

COMMON_DIR="$KERNEL_ROOT/common"
if [ ! -d "$COMMON_DIR" ] && [ -d "$KERNEL_ROOT/fs" ]; then
  COMMON_DIR="$KERNEL_ROOT"
fi

FS_DIR="$COMMON_DIR/fs"
DEFCONFIG="$COMMON_DIR/arch/arm64/configs/gki_defconfig"
NOMOUNT_DIR="$FS_DIR/nomount"

mkdir -p "$NOMOUNT_DIR"

# Source files from repository (local copy takes priority for reliability)
SRC_DIR="$GITHUB_WORKSPACE/kernel/nomount"
if [ -d "$SRC_DIR" ]; then
  echo "Copying NoMount source files from local repository ($SRC_DIR)..."
  cp -rf "$SRC_DIR/"* "$NOMOUNT_DIR/"
fi

# Verify critical driver source files exist, fallback to upstream if missing
if [ ! -f "$NOMOUNT_DIR/nomount.c" ] || [ ! -f "$NOMOUNT_DIR/nomount.h" ]; then
  echo "Fetching NoMount source from upstream repository..."
  curl -fsSL "https://raw.githubusercontent.com/maxsteeel/nomount/master/kernel/src/nomount.c" -o "$NOMOUNT_DIR/nomount.c" || \
  curl -fsSL "https://raw.githubusercontent.com/maxsteeel/nomount/dev/kernel/src/nomount.c" -o "$NOMOUNT_DIR/nomount.c"
  curl -fsSL "https://raw.githubusercontent.com/maxsteeel/nomount/master/kernel/src/nomount.h" -o "$NOMOUNT_DIR/nomount.h" || \
  curl -fsSL "https://raw.githubusercontent.com/maxsteeel/nomount/dev/kernel/src/nomount.h" -o "$NOMOUNT_DIR/nomount.h"
  curl -fsSL "https://raw.githubusercontent.com/maxsteeel/nomount/master/kernel/src/Makefile" -o "$NOMOUNT_DIR/Makefile" || \
  curl -fsSL "https://raw.githubusercontent.com/maxsteeel/nomount/dev/kernel/src/Makefile" -o "$NOMOUNT_DIR/Makefile"
  curl -fsSL "https://raw.githubusercontent.com/maxsteeel/nomount/master/kernel/src/Kconfig" -o "$NOMOUNT_DIR/Kconfig" || \
  curl -fsSL "https://raw.githubusercontent.com/maxsteeel/nomount/dev/kernel/src/Kconfig" -o "$NOMOUNT_DIR/Kconfig"
fi

if [ ! -f "$NOMOUNT_DIR/nomount.c" ]; then
  echo "::error::Failed to obtain NoMount driver source (nomount.c)"
  exit 1
fi

# 1. Update fs/Makefile
if ! grep -q "CONFIG_NOMOUNT" "$FS_DIR/Makefile"; then
  echo "Adding NoMount to fs/Makefile..."
  printf "\nobj-\$(CONFIG_NOMOUNT) += nomount/\n" >> "$FS_DIR/Makefile"
fi

# 2. Update fs/Kconfig
if ! grep -q 'source "fs/nomount/Kconfig"' "$FS_DIR/Kconfig"; then
  echo "Adding NoMount to fs/Kconfig..."
  python3 - "$FS_DIR/Kconfig" << 'PY'
import sys

kconfig_path = sys.argv[1]
with open(kconfig_path, "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()

entry = 'source "fs/nomount/Kconfig"\n'
if 'source "fs/nomount/Kconfig"' not in content:
    idx = content.rfind("endmenu")
    if idx != -1:
        new_content = content[:idx] + entry + "\n" + content[idx:]
    else:
        new_content = content + "\n" + entry
    with open(kconfig_path, "w", encoding="utf-8") as f:
        f.write(new_content)
PY
fi

# 3. Update defconfig
if [ -f "$DEFCONFIG" ]; then
  if ! grep -q "^CONFIG_NOMOUNT=y" "$DEFCONFIG"; then
    echo "Adding CONFIG_NOMOUNT=y to defconfig..."
    echo "CONFIG_NOMOUNT=y" >> "$DEFCONFIG"
  fi
fi

echo "✓ NoMount successfully integrated into kernel source!"
