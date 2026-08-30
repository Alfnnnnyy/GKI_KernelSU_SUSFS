#!/usr/bin/env python3
import os
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

    if "thermal_perf_filter_cdev_state(cdev->type, &state)" in content:
        print("✓ cpufreq_cooling.c already hooked")
        return

    needle = "target_freq = cpufreq_cdev->freq_table[state].frequency"
    if needle in content:
        idx = content.find(needle)
        line_start = content.rfind("\n", 0, idx) + 1
        content = content[:line_start] + "\tthermal_perf_filter_cdev_state(cdev->type, &state);\n" + content[line_start:]
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print("✓ Hooked cpufreq_cooling.c (Function Entry Hook)")
    else:
        print(f"::warning::Could not match {needle} in {filepath}")

def patch_devfreq_cooling(filepath):
    if not os.path.exists(filepath):
        print(f"::warning::{filepath} not found")
        return
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    decl = "extern void thermal_perf_filter_cdev_state(const char *type, unsigned long *state);\n"
    if "thermal_perf_filter_cdev_state" not in content:
        content = decl + content

    if "thermal_perf_filter_cdev_state(dfc->cdev->type, &state)" in content:
        print("✓ devfreq_cooling.c already hooked")
        return

    needle = "freq = dfc->freq_table[state]"
    if needle in content:
        idx = content.find(needle)
        line_start = content.rfind("\n", 0, idx) + 1
        content = content[:line_start] + "\tthermal_perf_filter_cdev_state(dfc->cdev->type, &state);\n" + content[line_start:]
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print("✓ Hooked devfreq_cooling.c (GPU Devfreq Cooling Zero-Throttle Override)")
    else:
        print(f"::warning::Could not match {needle} in {filepath}")

def patch_thermal_sysfs(filepath):
    if not os.path.exists(filepath):
        print(f"::warning::{filepath} not found")
        return
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    decl = "extern void thermal_perf_filter_cdev_state(const char *type, unsigned long *state);\n"
    if "thermal_perf_filter_cdev_state" not in content:
        content = decl + content

    if "thermal_perf_filter_cdev_state(cdev->type, &state)" in content:
        print("✓ thermal_sysfs.c already hooked")
        return

    fn_needle = "cur_state_store"
    if fn_needle in content:
        idx = content.find(fn_needle)
        kstrtoul_needle = "kstrtoul"
        kstr_idx = content.find(kstrtoul_needle, idx)
        if kstr_idx != -1:
            semi_idx = content.find(";", kstr_idx)
            if_idx = content.find("if (", semi_idx)
            if_end_idx = content.find("\n", if_idx)
            content = content[:if_end_idx+1] + "\tthermal_perf_filter_cdev_state(cdev->type, &state);\n" + content[if_end_idx+1:]
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print("✓ Hooked thermal_sysfs.c (Userspace Cooling Device Sysfs Write Hook)")
            return
    print(f"::warning::Could not match cur_state_store in {filepath}")

def patch_power_supply_core(filepath):
    if not os.path.exists(filepath):
        print(f"::warning::{filepath} not found")
        return
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    decl = "extern int thermal_perf_filter_power_supply_prop(int psp, const union power_supply_propval *val);\n"
    if "thermal_perf_filter_power_supply_prop" not in content:
        content = decl + content

    if "thermal_perf_filter_power_supply_prop(psp, val)" in content:
        print("✓ power_supply_core.c already hooked")
        return

    hook_code = """
	if (thermal_perf_filter_power_supply_prop(psp, val))
		return 0;
"""
    fn_needle = "int power_supply_set_property"
    if fn_needle in content:
        idx = content.find(fn_needle)
        brace_idx = content.find("{", idx)
        content = content[:brace_idx+1] + hook_code + content[brace_idx+1:]
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print("✓ Hooked power_supply_core.c (Universal PMIC Charge Control Limit Bypass Hook)")
    else:
        print(f"::warning::Could not match power_supply_set_property in {filepath}")

def patch_cpufreq_core(filepath):
    if not os.path.exists(filepath):
        print(f"::warning::{filepath} not found")
        return
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    if "thermal_perf_get_mode" in content:
        print("✓ cpufreq.c already hooked")
        return

    fn_needle = "cpufreq_set_policy"
    fn_pos = content.find(fn_needle)
    if fn_pos != -1:
        # Match Linux 6.1+ PM QoS pattern
        qos_needle = "FREQ_QOS_MAX);"
        idx = content.find(qos_needle, fn_pos)
        if idx != -1:
            semi_idx = idx + len(qos_needle)
            hook_code = f"""
\t{{
\t\textern int thermal_perf_get_mode(void);
\t\tint tp_mode = thermal_perf_get_mode();
\t\tif (tp_mode == 2) {{
\t\t\tnew_data.min = policy->cpuinfo.max_freq;
\t\t\tnew_data.max = policy->cpuinfo.max_freq;
\t\t}} else if (tp_mode == 0) {{
\t\t\tnew_data.max = (policy->cpuinfo.max_freq * 70) / 100;
\t\t}}
\t}}
"""
            content = content[:semi_idx] + hook_code + content[semi_idx:]
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print("✓ Hooked cpufreq.c (cpufreq_set_policy PM QoS FREQ_QOS_MAX Override)")
            return

        # Fallback for older 5.10 notifier pattern
        idx = content.find("CPUFREQ_ADJUST", fn_pos)
        if idx != -1:
            semi_idx = content.find(";", idx)
            call_text = content[idx:semi_idx]
            dot_or_arrow = "." if "&" in call_text else "->"
            hook_code = f"""
\t{{
\t\textern int thermal_perf_get_mode(void);
\t\tint tp_mode = thermal_perf_get_mode();
\t\tif (tp_mode == 2) {{
\t\t\tnew_policy{dot_or_arrow}min = policy->cpuinfo.max_freq;
\t\t\tnew_policy{dot_or_arrow}max = policy->cpuinfo.max_freq;
\t\t}} else if (tp_mode == 0) {{
\t\t\tnew_policy{dot_or_arrow}max = (policy->cpuinfo.max_freq * 70) / 100;
\t\t}}
\t}}
"""
            content = content[:semi_idx+1] + hook_code + content[semi_idx+1:]
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print("✓ Hooked cpufreq.c (cpufreq_set_policy CPUFREQ_ADJUST Override)")
            return
    print(f"::warning::Could not match cpufreq_set_policy in {filepath}")

if __name__ == "__main__":
    common_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    patch_cpufreq_cooling(os.path.join(common_dir, "drivers/thermal/cpufreq_cooling.c"))
    patch_devfreq_cooling(os.path.join(common_dir, "drivers/thermal/devfreq_cooling.c"))
    patch_thermal_sysfs(os.path.join(common_dir, "drivers/thermal/thermal_sysfs.c"))
    patch_power_supply_core(os.path.join(common_dir, "drivers/power/supply/power_supply_core.c"))
    patch_cpufreq_core(os.path.join(common_dir, "drivers/cpufreq/cpufreq.c"))
