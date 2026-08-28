#!/usr/bin/env python3
import os
import re
import sys

def patch_file(filepath, fn_signature, label):
    if not os.path.exists(filepath):
        print(f"::warning::{filepath} not found")
        return
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    if "thermal_perf_get_mode" not in content:
        content = "extern int thermal_perf_get_mode(void);\n" + content

    fn_pattern = re.compile(rf'({fn_signature}[\s\S]*?\{{)([\s\S]*?)(if\s*\()')
    fn_match = fn_pattern.search(content)
    if fn_match and "thermal_perf_get_mode() == 2" not in content:
        prefix = fn_match.group(1)
        decls = fn_match.group(2)
        if_stmt = fn_match.group(3)
        replacement = prefix + decls + "\tif (thermal_perf_get_mode() == 2)\n\t\tstate = 0;\n\n\t" + if_stmt
        content = content.replace(fn_match.group(0), replacement, 1)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✓ Hooked {label} for zero throttling in Game Mode")
    elif "thermal_perf_get_mode() == 2" in content:
        print(f"✓ {label} already hooked")
    else:
        print(f"::warning::Could not match {fn_signature} in {filepath}")

if __name__ == "__main__":
    common_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    cpufreq_c = os.path.join(common_dir, "drivers/thermal/cpufreq_cooling.c")
    devfreq_c = os.path.join(common_dir, "drivers/thermal/devfreq_cooling.c")
    patch_file(cpufreq_c, "cpufreq_set_cur_state", "cpufreq_cooling.c")
    patch_file(devfreq_c, "devfreq_cooling_set_cur_state", "devfreq_cooling.c")
