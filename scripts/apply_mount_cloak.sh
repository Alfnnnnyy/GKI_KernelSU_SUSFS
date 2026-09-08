#!/usr/bin/env bash
# Universal OverlayFS Procfs Cloak for /proc/self/mountinfo, /proc/mounts, /proc/self/mountstats
# Omits overlay entries (e.g. Xiaomi mi_ext / root mount markers) via Linux SEQ_SKIP
# Usage: bash scripts/apply_mount_cloak.sh <kernel_root>

set -eo pipefail

KERNEL_ROOT="${1:-$GITHUB_WORKSPACE}"
COMMON_DIR="$KERNEL_ROOT/common"

echo "Applying procfs mountinfo overlay cloaking..."

python3 - <<PY
import os, re

common_dir = "$COMMON_DIR"
target_c = os.path.join(common_dir, "fs/proc_namespace.c")

if os.path.exists(target_c):
    with open(target_c, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    if "SEQ_SKIP: completely omit overlay entries" in content:
        print("✓ fs/proc_namespace.c already cloaked")
    else:
        # 1. Add #include <linux/string.h> if not present
        if "#include <linux/string.h>" not in content:
            content = "#include <linux/string.h>\n" + content

        hook_code = '''\tif (sb && sb->s_type && sb->s_type->name && !strcmp(sb->s_type->name, "overlay")) {
\t\treturn 1; /* SEQ_SKIP: completely omit overlay entries */
\t}
'''

        success_count = 0
        for fn in ['show_mountinfo', 'show_vfsmnt', 'show_vfsstat']:
            pattern = re.compile(r'(static\s+int\s+' + fn + r'\s*\([^)]*\)\s*\{[\s\S]*?int\s+err\s*;[\r\n]+)')
            if pattern.search(content):
                content = pattern.sub(r'\1' + hook_code, content, count=1)
                success_count += 1
                print(f"✓ Hooked {fn} in fs/proc_namespace.c")
            else:
                print(f"::warning::Could not find {fn} declaration in fs/proc_namespace.c")

        if success_count > 0:
            with open(target_c, "w", encoding="utf-8") as f:
                f.write(content)
            print("✓ Successfully cloaked overlayfs in fs/proc_namespace.c")
else:
    print(f"::warning::{target_c} does not exist")
PY
