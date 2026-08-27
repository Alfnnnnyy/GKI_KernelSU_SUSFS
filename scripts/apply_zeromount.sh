#!/usr/bin/env bash
# Apply ZeroMount Kernel Patch (VFS Path Redirection via /dev/zeromount)
# Usage: bash scripts/apply_zeromount.sh <android_version> <kernel_version> <kernel_root>

set -eo pipefail

ANDROID_VER="${1:-android14}"
KERNEL_VER="${2:-6.1}"
KERNEL_ROOT="${3:-$GITHUB_WORKSPACE}"

echo "========================================"
echo "      ZeroMount Patch Application       "
echo "========================================"
echo "Android Version : $ANDROID_VER"
echo "Kernel Version  : $KERNEL_VER"
echo "Kernel Root     : $KERNEL_ROOT"
echo "========================================"

COMMON_DIR="$KERNEL_ROOT/common"
DEFCONFIG="$COMMON_DIR/arch/arm64/configs/gki_defconfig"
PATCH_FILE="$GITHUB_WORKSPACE/patches/zeromount/60_zeromount-${ANDROID_VER}-${KERNEL_VER}.patch"

if [ ! -f "$PATCH_FILE" ]; then
  # Fallback search by kernel version
  PATCH_FILE=$(find "$GITHUB_WORKSPACE/patches/zeromount" -name "*${KERNEL_VER}*.patch" | head -n 1)
fi

if [ -z "$PATCH_FILE" ] || [ ! -f "$PATCH_FILE" ]; then
  echo "::error::ZeroMount patch not found for ${ANDROID_VER}-${KERNEL_VER}"
  exit 1
fi

echo "Applying patch: $PATCH_FILE"
cd "$COMMON_DIR"

# Apply patch (forward only, non-fatal if partial/already applied)
patch -p1 --forward < "$PATCH_FILE" || {
  echo "::warning::Some hunks were already applied or fuzzy. Verifying critical files..."
}

# Verify driver source was created
if [ ! -f "fs/zeromount.c" ]; then
  echo "::error::fs/zeromount.c was not created by patch!"
  exit 1
fi

if [ ! -f "include/linux/zeromount.h" ]; then
  echo "::error::include/linux/zeromount.h was not created by patch!"
  exit 1
fi

# Fix potential orphaned zm_out label in fs/readdir.c across all 5.x / 6.x kernels
if [ -f "fs/readdir.c" ]; then
  # If zm_out label exists but goto zm_out was rejected in some sublevel functions
  # remove orphaned zm_out labels that have no matching goto
  python3 - <<'PY'
import re

with open("fs/readdir.c", "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()

# Check function by function
func_pattern = re.compile(r'((?:SYSCALL_DEFINE3|COMPAT_SYSCALL_DEFINE3)\s*\(\s*getdents(?:64)?[\s\S]*?^})', re.MULTILINE)

def fix_func(match):
    fn_body = match.group(1)
    if "zm_out:" in fn_body and "goto zm_out;" not in fn_body:
        print("Fixing orphaned zm_out in getdents function...")
        # Remove orphaned zm_out label
        fn_body = re.sub(r'#ifdef CONFIG_ZEROMOUNT\s+zm_out:\s+#endif', '', fn_body)
        fn_body = re.sub(r'^\s*zm_out:\s*', '', fn_body, flags=re.MULTILINE)
    return fn_body

fixed_content = func_pattern.sub(fix_func, content)
with open("fs/readdir.c", "w", encoding="utf-8") as f:
    f.write(fixed_content)
PY
fi

# Suppress unused-label warnings across 5.x Makefile
if [ -f "Makefile" ]; then
  sed -i '/KBUILD_CFLAGS\s*+=/a KBUILD_CFLAGS += -Wno-error=unused-label -Wno-unused-label' Makefile 2>/dev/null || true
fi

# Ensure Makefile has obj-$(CONFIG_ZEROMOUNT) += zeromount.o
if ! grep -q "CONFIG_ZEROMOUNT" fs/Makefile; then
  echo "Adding zeromount.o to fs/Makefile..."
  echo "obj-\$(CONFIG_ZEROMOUNT) += zeromount.o" >> fs/Makefile
fi

# Ensure Kconfig has config ZEROMOUNT
if ! grep -q "config ZEROMOUNT" fs/Kconfig; then
  echo "Adding config ZEROMOUNT to fs/Kconfig..."
  sed -i '/endmenu/i \nconfig ZEROMOUNT
	bool "ZeroMount Path Redirection Subsystem"
	default y
	help
	  ZeroMount allows path redirection and virtual file injection
	  without mounting filesystems. Useful for systemless modifications.
' fs/Kconfig
fi

# Ensure defconfig has CONFIG_ZEROMOUNT=y
if ! grep -q "^CONFIG_ZEROMOUNT=y" "$DEFCONFIG"; then
  echo "CONFIG_ZEROMOUNT=y" >> "$DEFCONFIG"
fi

echo "✓ ZeroMount successfully integrated into kernel source!"
