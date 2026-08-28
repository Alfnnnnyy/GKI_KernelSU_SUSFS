#!/usr/bin/env python3
import os
import re
import sys

def inject_decl_and_hook(filepath, hook_decl, search_pattern, hook_code, label):
    if not os.path.exists(filepath):
        print(f"::warning::{filepath} not found (skipped {label})")
        return False

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    if hook_decl not in content:
        content = f"{hook_decl}\n" + content

    if hook_code.strip() in content:
        print(f"✓ {label} already hooked")
        return True

    match = re.search(search_pattern, content)
    if match:
        content = content[:match.end()] + "\n" + hook_code + content[match.end():]
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✓ Hooked {label}")
        return True
    else:
        print(f"::warning::Could not match pattern for {label} in {filepath}")
        return False

def patch_cooling_framework(common_dir):
    decl = "extern void thermal_perf_filter_cdev_state(const char *type, unsigned long *state);"
    fc_decl = "extern int thermal_perf_get_fastcharge(void);\nextern int thermal_perf_get_mode(void);"

    # 1. Hook cpufreq_cooling.c
    cpufreq_c = os.path.join(common_dir, "drivers/thermal/cpufreq_cooling.c")
    hook_cpufreq = "\tthermal_perf_filter_cdev_state(cdev->type, &state);\n"
    inject_decl_and_hook(
        cpufreq_c,
        decl,
        r'cpufreq_set_cur_state\s*\([^)]*\)\s*\{[^}]*?struct freq_qos_request\s*\*[a-zA-Z0-9_]+\s*=\s*&[a-zA-Z0-9_]+->qos_req;',
        hook_cpufreq,
        "cpufreq_cooling.c (CPU Frequency Cooling)"
    )

    # 2. Hook devfreq_cooling.c
    devfreq_c = os.path.join(common_dir, "drivers/thermal/devfreq_cooling.c")
    hook_devfreq = "\tthermal_perf_filter_cdev_state(cdev->type, &state);\n"
    inject_decl_and_hook(
        devfreq_c,
        decl,
        r'devfreq_cooling_set_cur_state\s*\([^)]*\)\s*\{',
        hook_devfreq,
        "devfreq_cooling.c (GPU Devfreq Cooling)"
    )

    # 3. Hook thermal_sysfs.c (Intercepts userspace mi_thermald / sysfs writes)
    thermal_sysfs_c = os.path.join(common_dir, "drivers/thermal/thermal_sysfs.c")
    hook_sysfs = "\tthermal_perf_filter_cdev_state(cdev->type, &state);\n"
    inject_decl_and_hook(
        thermal_sysfs_c,
        decl,
        r'cur_state_store\s*\([^)]*\)\s*\{[^}]*?if\s*\(\s*kstrtoul\s*\([^)]*\)\s*<[^)]*\)\s*return\s*-EINVAL\s*;',
        hook_sysfs,
        "thermal_sysfs.c (Userspace Cooling Device Sysfs Write Hook)"
    )

    # 4. Hook thermal_helpers.c (Intercepts in-kernel governor throttling calculations)
    thermal_helpers_c = os.path.join(common_dir, "drivers/thermal/thermal_helpers.c")
    hook_helpers = "\tthermal_perf_filter_cdev_state(cdev->type, &cdev->target_order);\n"
    # Try hooking __thermal_cooling_device_update or thermal_zone_trip_update
    inject_decl_and_hook(
        thermal_helpers_c,
        decl,
        r'void\s+__thermal_cooling_device_update\s*\([^)]*\)\s*\{',
        "\tthermal_perf_filter_cdev_state(cdev->type, &cdev->target);\n",
        "thermal_helpers.c (__thermal_cooling_device_update)"
    )

    # 5. Hook power_supply_sysfs.c (Intercepts userspace PMIC charge_control_limit / FCC writes)
    power_sysfs_c = os.path.join(common_dir, "drivers/power/supply/power_supply_sysfs.c")
    hook_power = """\tif (thermal_perf_get_fastcharge() == 1 || thermal_perf_get_mode() == 2) {
\t\tif (off == POWER_SUPPLY_PROP_CHARGE_CONTROL_LIMIT) {
\t\t\tvalue.intval = 0;
\t\t}
\t}
"""
    inject_decl_and_hook(
        power_sysfs_c,
        fc_decl,
        r'static\s+ssize_t\s+power_supply_store_property\s*\([^)]*\)\s*\{[^}]*?ret\s*=\s*kstrtoint\s*\([^)]*\)\s*;\s*if\s*\(ret\)\s*return\s*ret\s*;',
        hook_power,
        "power_supply_sysfs.c (PMIC Charge Control Limit Bypass Hook)"
    )

if __name__ == "__main__":
    common_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    patch_cooling_framework(common_dir)
