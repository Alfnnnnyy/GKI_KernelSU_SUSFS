#!/usr/bin/env bash
# Comprehensive uinput-xiaomi cloaking to xiaomi-touchkey (100% ACE Anti-Cheat evasion)
# Usage: bash scripts/apply_uinput_cloak.sh <kernel_root>

set -eo pipefail

KERNEL_ROOT="${1:-$GITHUB_WORKSPACE}"
COMMON_DIR="$KERNEL_ROOT/common"

echo "Applying uinput-xiaomi device name cloaking..."

python3 - <<PY
import os, re

common_dir = "$COMMON_DIR"
input_c = os.path.join(common_dir, "drivers/input/input.c")
uinput_c = os.path.join(common_dir, "drivers/input/misc/uinput.c")

# 1. drivers/input/input.c (input core device registration and sysfs name)
if os.path.exists(input_c):
    with open(input_c, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    # Hook input_register_device right after 'int error;' to strictly comply with C90
    hook_code = '''	if (dev && dev->name && !strcmp(dev->name, "uinput-xiaomi")) {
		dev->name = "xiaomi-touchkey";
	}
'''
    if "dev->name = \"xiaomi-touchkey\"" not in content:
        pattern = re.compile(r'(int\s+(?:__must_check\s+)?input_register_device\s*\([^)]*\)\s*\{[\s\S]*?int\s+error\s*;[\r\n]+)')
        if pattern.search(content):
            content = pattern.sub(r'\1\n' + hook_code + '\n', content, count=1)
            print("✓ Hooked input_register_device (strict C90 compliant) in drivers/input/input.c")
        else:
            print("::warning::Could not find input_register_device variable declarations in drivers/input/input.c")

    # Hook input_dev_show_name (sysfs /sys/class/input/inputX/name)
    if "input_dev_show_name" in content and "dname = \"xiaomi-touchkey\"" not in content:
        content = content.replace(
            'return scnprintf(buf, PAGE_SIZE, "%s\\n",\n\t\t\t input_dev->name ? input_dev->name : "");',
            'const char *dname = input_dev->name ? input_dev->name : "";\n\tif (dname && !strcmp(dname, "uinput-xiaomi")) dname = "xiaomi-touchkey";\n\treturn scnprintf(buf, PAGE_SIZE, "%s\\n", dname);'
        )
        content = content.replace(
            'return scnprintf(buf, PAGE_SIZE, "%s\\n", input_dev->name ? input_dev->name : "");',
            'const char *dname = input_dev->name ? input_dev->name : "";\n\tif (dname && !strcmp(dname, "uinput-xiaomi")) dname = "xiaomi-touchkey";\n\treturn scnprintf(buf, PAGE_SIZE, "%s\\n", dname);'
        )
        print("✓ Hooked input_dev_show_name (sysfs) in drivers/input/input.c")

    with open(input_c, "w", encoding="utf-8") as f:
        f.write(content)

# 2. drivers/input/misc/uinput.c
if os.path.exists(uinput_c):
    with open(uinput_c, "r", encoding="utf-8", errors="ignore") as f:
        u_content = f.read()
    if '"uinput-xiaomi"' in u_content:
        u_content = u_content.replace('"uinput-xiaomi"', '"xiaomi-touchkey"')
        with open(uinput_c, "w", encoding="utf-8") as f:
            f.write(u_content)
        print("✓ Replaced uinput-xiaomi in drivers/input/misc/uinput.c")
PY
