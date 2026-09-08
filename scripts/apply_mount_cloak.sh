#!/usr/bin/env bash
# Universal OverlayFS Procfs Cloak for /proc/self/mountinfo, /proc/mounts, /proc/self/mountstats
# Transforms overlay entries (e.g. Xiaomi mi_ext) into seamless 'erofs' entries without dropping lines
# Sanitizes any path-level 'overlay' strings in-place (e.g. /product/overlay -> /product/app_rro)
# Preserves 100% contiguous mount IDs and Peer Groups (0 Peer Group Gaps for Duck Detector)
# Usage: bash scripts/apply_mount_cloak.sh <kernel_root>

set -eo pipefail

KERNEL_ROOT="${1:-$GITHUB_WORKSPACE}"
COMMON_DIR="$KERNEL_ROOT/common"

echo "Applying procfs mountinfo overlay -> erofs seamless cloaking..."

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

    # 2. Hook show_type: transform filesystem type 'overlay' -> 'erofs'
    if 'mangle(m, "erofs");' not in content:
        show_type_hook = '''static void show_type(struct seq_file *m, struct super_block *sb)
{
\tif (sb && sb->s_type && sb->s_type->name && !strcmp(sb->s_type->name, "overlay")) {
\t\tmangle(m, "erofs");
\t\treturn;
\t}
'''
        content = re.sub(r'static\s+void\s+show_type\s*\([^)]*\)\s*\{[\r\n]+', show_type_hook, content, count=1)
        print("✓ Hooked show_type in fs/proc_namespace.c (mangles 'overlay' -> 'erofs')")

    # 3. Replace devname 'overlay' -> 'none'
    old_devname = 'mangle(m, r->mnt_devname ? r->mnt_devname : "none");'
    new_devname = '''{
\t\tconst char *devn = r->mnt_devname ? r->mnt_devname : "none";
\t\tif (sb && sb->s_type && sb->s_type->name && !strcmp(sb->s_type->name, "overlay"))
\t\t\tdevn = "none";
\t\tmangle(m, devn);
\t}'''
    if old_devname in content:
        content = content.replace(old_devname, new_devname)
        print("✓ Replaced r->mnt_devname in fs/proc_namespace.c")

    # 4. Suppress show_options for overlayfs (strips lowerdir=... completely)
    pattern_opts = re.compile(r'if\s*\(\s*sb->s_op->show_options\s*\)\s*(\n\s*err\s*=\s*sb->s_op->show_options\s*\([^)]+\)\s*;)')
    if pattern_opts.search(content):
        content = pattern_opts.sub(r'if (sb->s_op->show_options && (!sb->s_type || !sb->s_type->name || strcmp(sb->s_type->name, "overlay")))\1', content)
        print("✓ Suppressed lowerdir/upperdir in fs/proc_namespace.c show_options")

    # 5. In-place string sanitization for path-level 'overlay' (e.g. /product/overlay -> /product/app_rro)
    if 'ovl_i <= m->count - 7' not in content:
        sanitize_code = """\t{
\t\tsize_t ovl_i;
\t\tif (m->count >= 7) {
\t\t\tfor (ovl_i = 0; ovl_i <= m->count - 7; ovl_i++) {
\t\t\t\tif (m->buf[ovl_i] == 'o' && !memcmp(&m->buf[ovl_i], "overlay", 7)) {
\t\t\t\t\tmemcpy(&m->buf[ovl_i], "app_rro", 7);
\t\t\t\t\tovl_i += 6;
\t\t\t\t}
\t\t\t}
\t\t}
\t}
out:
\treturn err;"""
        n1 = "\tseq_putc(m, '\\n');\nout:\n\treturn err;"
        n2 = '\tseq_puts(m, " 0 0\\n");\nout:\n\treturn err;'
        new_n1 = "\tseq_putc(m, '\\n');\n" + sanitize_code
        new_n2 = '\tseq_puts(m, " 0 0\\n");\n' + sanitize_code
        content = content.replace(n1, new_n1).replace(n2, new_n2)
        print("✓ Injected in-place path sanitization (overlay -> app_rro) to all mount output functions")

    # 6. Remove any legacy SEQ_SKIP line drops to keep mount IDs and peer groups 100% contiguous
    content = re.sub(r'\tif \(sb && sb->s_type && sb->s_type->name && !strcmp\(sb->s_type->name, "overlay"\)\) \{\n\t\treturn 1; /\* SEQ_SKIP[^\n]+\n\t\}\n', '', content)

    with open(target_c, "w", encoding="utf-8") as f:
        f.write(content)
    print("✓ Successfully applied seamless overlay -> erofs cloaking to fs/proc_namespace.c")
else:
    print(f"::warning::{target_c} does not exist")
PY
