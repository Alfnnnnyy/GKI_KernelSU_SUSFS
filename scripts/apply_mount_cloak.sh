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

    # 1. Add #include <linux/string.h> if not present
    if "#include <linux/string.h>" not in content:
        content = "#include <linux/string.h>\n" + content

    hook_code = '''\tif (sb && sb->s_type && sb->s_type->name && !strcmp(sb->s_type->name, "overlay")) {
\t\treturn 1; /* SEQ_SKIP: completely omit overlay entries */
\t}
'''

    success_count = 0
    for fn in ['show_mountinfo', 'show_vfsmnt', 'show_vfsstat',
               'susfs_show_mountinfo', 'susfs_show_vfsmnt', 'susfs_show_vfsstat']:
        pattern = re.compile(r'(static\s+int\s+' + fn + r'\s*\([^)]*\)\s*\{[\s\S]*?int\s+err\s*;[\r\n]+)')
        match = pattern.search(content)
        if match:
            fn_start = match.start()
            fn_head = content[fn_start:fn_start+350]
            if "SEQ_SKIP: completely omit overlay entries" not in fn_head:
                insert_pos = match.end()
                content = content[:insert_pos] + hook_code + content[insert_pos:]
                success_count += 1
                print(f"✓ Hooked {fn} in fs/proc_namespace.c (SEQ_SKIP)")

    # 2. Defense-in-depth: hook show_type to never emit 'overlay'
    if 'mangle(m, "erofs");' not in content:
        show_type_hook = '''static void show_type(struct seq_file *m, struct super_block *sb)
{
\tif (sb && sb->s_type && sb->s_type->name && !strcmp(sb->s_type->name, "overlay")) {
\t\tmangle(m, "erofs");
\t\treturn;
\t}
'''
        content = re.sub(r'static\s+void\s+show_type\s*\([^)]*\)\s*\{[\r\n]+', show_type_hook, content, count=1)
        success_count += 1
        print("✓ Hooked show_type in fs/proc_namespace.c (mangles 'overlay' -> 'erofs')")

    if success_count > 0:
        with open(target_c, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✓ Successfully cloaked overlayfs in fs/proc_namespace.c ({success_count} hooks applied)")
    else:
        print("✓ fs/proc_namespace.c already fully cloaked")
else:
    print(f"::warning::{target_c} does not exist")
PY
