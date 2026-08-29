#!/usr/bin/env python3
import os
import re
import sys

def patch_cpufreq_cooling(filepath):
    if not os.path.exists(filepath):
        print(f"::warning::{filepath} not found")
        return
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    decl = "extern void thermal_perf_filter_cdev_state(const char *type, unsigned long *state);\n"
    if "thermal_perf_filter_cdev_state" not in content:
        content = decl + content

    hook = "\n\tthermal_perf_filter_cdev_state(cdev->type, &state);"
    pattern = re.compile(r'(cpufreq_set_cur_state[\s\S]*?\{)')
    match = pattern.search(content)
    if match and "thermal_perf_filter_cdev_state(cdev->type, &state)" not in content:
        content = content[:match.end()] + hook + content[match.end():]
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print("✓ Hooked cpufreq_cooling.c (CPU Frequency Cooling Zero-Throttle Override)")
    elif "thermal_perf_filter_cdev_state(cdev->type, &state)" in content:
        print("✓ cpufreq_cooling.c already hooked")
    else:
        print(f"::error::Could not find cpufreq_set_cur_state in {filepath}")
        sys.exit(1)

def patch_devfreq_cooling(filepath):
    if not os.path.exists(filepath):
        print(f"::warning::{filepath} not found")
        return
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    decl = "extern void thermal_perf_filter_cdev_state(const char *type, unsigned long *state);\n"
    if "thermal_perf_filter_cdev_state" not in content:
        content = decl + content

    hook = "\n\tthermal_perf_filter_cdev_state(cdev->type, &state);"
    pattern = re.compile(r'(devfreq_cooling_set_cur_state[\s\S]*?\{)')
    match = pattern.search(content)
    if match and "thermal_perf_filter_cdev_state(cdev->type, &state)" not in content:
        content = content[:match.end()] + hook + content[match.end():]
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print("✓ Hooked devfreq_cooling.c (GPU Devfreq Cooling Zero-Throttle Override)")
    elif "thermal_perf_filter_cdev_state(cdev->type, &state)" in content:
        print("✓ devfreq_cooling.c already hooked")
    else:
        print(f"::error::Could not find devfreq_cooling_set_cur_state in {filepath}")
        sys.exit(1)

def patch_thermal_sysfs(filepath):
    if not os.path.exists(filepath):
        print(f"::warning::{filepath} not found")
        return
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    decl = "extern void thermal_perf_filter_cdev_state(const char *type, unsigned long *state);\n"
    if "thermal_perf_filter_cdev_state" not in content:
        content = decl + content

    hook = "\n\tthermal_perf_filter_cdev_state(cdev->type, &state);"
    pattern = re.compile(r'(cur_state_store[\s\S]*?\{)')
    match = pattern.search(content)
    if match and "thermal_perf_filter_cdev_state(cdev->type, &state)" not in content:
        content = content[:match.end()] + hook + content[match.end():]
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print("✓ Hooked thermal_sysfs.c (Userspace Cooling Device Sysfs Write Hook)")
    elif "thermal_perf_filter_cdev_state(cdev->type, &state)" in content:
        print("✓ thermal_sysfs.c already hooked")

def patch_power_supply_core(filepath):
    if not os.path.exists(filepath):
        print(f"::warning::{filepath} not found")
        return
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    fc_decl = "extern int thermal_perf_get_fastcharge(void);\nextern int thermal_perf_get_mode(void);\n"
    if "thermal_perf_get_fastcharge" not in content:
        content = fc_decl + content

    hook_code = """
	union power_supply_propval tp_override_val;
	if (thermal_perf_get_fastcharge() == 1 || thermal_perf_get_mode() == 2) {
		if (psp == POWER_SUPPLY_PROP_CHARGE_CONTROL_LIMIT) {
			tp_override_val.intval = 0;
			val = &tp_override_val;
		}
	}
"""
    pattern = re.compile(r'(int\s+power_supply_set_property[\s\S]*?\{)')
    match = pattern.search(content)
    if match and "thermal_perf_get_fastcharge" not in content[match.end():match.end()+350]:
        content = content[:match.end()] + hook_code + content[match.end():]
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print("✓ Hooked power_supply_core.c (Universal PMIC Charge Control Limit Bypass Hook)")
    elif "POWER_SUPPLY_PROP_CHARGE_CONTROL_LIMIT" in content and "thermal_perf_get_fastcharge" in content:
        print("✓ power_supply_core.c already hooked")
    else:
        print(f"::warning::Could not match power_supply_set_property in {filepath}")

if __name__ == "__main__":
    common_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    patch_cpufreq_cooling(os.path.join(common_dir, "drivers/thermal/cpufreq_cooling.c"))
    patch_devfreq_cooling(os.path.join(common_dir, "drivers/thermal/devfreq_cooling.c"))
    patch_thermal_sysfs(os.path.join(common_dir, "drivers/thermal/thermal_sysfs.c"))
    patch_power_supply_core(os.path.join(common_dir, "drivers/power/supply/power_supply_core.c"))
