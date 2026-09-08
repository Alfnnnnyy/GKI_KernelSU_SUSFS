#!/usr/bin/env bash
set -eo pipefail

KERNEL_ROOT="${1:-$GITHUB_WORKSPACE}"
echo "Applying procfs mountinfo overlay -> erofs seamless cloaking..."
python3 "$GITHUB_WORKSPACE/scripts/patch_mountinfo.py" "$KERNEL_ROOT"
