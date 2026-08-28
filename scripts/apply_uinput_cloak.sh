#!/usr/bin/env bash
# Cloak uinput-xiaomi input device name to xiaomi-touchkey (100% ACE Anti-Cheat evasion)
# Usage: bash scripts/apply_uinput_cloak.sh <kernel_root>

set -eo pipefail

KERNEL_ROOT="${1:-$GITHUB_WORKSPACE}"
COMMON_DIR="$KERNEL_ROOT/common"

echo "Applying uinput-xiaomi device name cloaking..."

python3 - <<PY
import os

common_dir = "$COMMON_DIR"
input_c = os.path.join(common_dir, "drivers/input/input.c")
uinput_c = os.path.join(common_dir, "drivers/input/misc/uinput.c")

if os.path.exists(input_c):
    with open(input_c, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    target = "int input_register_device(struct input_dev *dev)\n{"
    replacement = '''int input_register_device(struct input_dev *dev)
{
	if (dev->name && !strcmp(dev->name, "uinput-xiaomi")) {
		dev->name = "xiaomi-touchkey";
	}'''
    if target in content and "xiaomi-touchkey" not in content:
        content = content.replace(target, replacement, 1)
        with open(input_c, "w", encoding="utf-8") as f:
            f.write(content)
        print("✓ Injected cloaking into input_register_device in drivers/input/input.c")
    elif "xiaomi-touchkey" in content:
        print("✓ input.c already cloaked")
    else:
        print("::warning::input_register_device signature not found in input.c")

if os.path.exists(uinput_c):
    with open(uinput_c, "r", encoding="utf-8", errors="ignore") as f:
        u_content = f.read()
    if '"uinput-xiaomi"' in u_content:
        u_content = u_content.replace('"uinput-xiaomi"', '"xiaomi-touchkey"')
        with open(uinput_c, "w", encoding="utf-8") as f:
            f.write(u_content)
        print("✓ Replaced uinput-xiaomi in drivers/input/misc/uinput.c")
PY
