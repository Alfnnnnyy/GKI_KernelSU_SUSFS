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

    # Find target_freq = cpufreq_cdev->freq_table[state].frequency
    needle = "target_freq = cpufreq_cdev->freq_table[state].frequency"
    if needle in content:
        idx = content.find(needle)
        line_start = content.rfind("\n", 0, idx) + 1
        content = content[:line_start] + "\tthermal_perf_filter_cdev_state(cdev->type, &state);\n" + content[line_start:]
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print("✓ Hooked cpufreq_cooling.c (CPU Frequency Cooling Zero-Throttle Override)")
    else:
        # Fallback to cpufreq_set_cur_state function body
        fn_needle = "int cpufreq_set_cur_state"
        if fn_needle in content:
            idx = content.find(fn_needle)
            brace_idx = content.find("{", idx)
            content = content[:brace_idx+1] + "\n\tthermal_perf_filter_cdev_state(cdev->type, &state);" + content[brace_idx+1:]
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print("✓ Hooked cpufreq_cooling.c (Function Entry Hook)")
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

    if "thermal_perf_filter_cdev_state(cdev->type, &state)" in content:
        print("✓ devfreq_cooling.c already hooked")
        return

    fn_needle = "int devfreq_cooling_set_cur_state"
    if fn_needle in content:
        idx = content.find(fn_needle)
        brace_idx = content.find("{", idx)
        content = content[:brace_idx+1] + "\n\tthermal_perf_filter_cdev_state(cdev->type, &state);" + content[brace_idx+1:]
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print("✓ Hooked devfreq_cooling.c (GPU Devfreq Cooling Zero-Throttle Override)")
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

    if "thermal_perf_filter_cdev_state(cdev->type, &state)" in content:
        print("✓ thermal_sysfs.c already hooked")
        return

    # Find cdev->ops->set_cur_state call
    needle = "cdev->ops->set_cur_state"
    if needle in content:
        idx = content.find(needle)
        line_start = content.rfind("\n", 0, idx) + 1
        content = content[:line_start] + "\tthermal_perf_filter_cdev_state(cdev->type, &state);\n" + content[line_start:]
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print("✓ Hooked thermal_sysfs.c (Userspace Cooling Device Sysfs Write Hook)")
    else:
        print(f"::warning::Could not match cdev->ops->set_cur_state in {filepath}")

def patch_power_supply_core(filepath):
    if not os.path.exists(filepath):
        print(f"::warning::{filepath} not found")
        return
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    fc_decl = "extern int thermal_perf_get_fastcharge(void);\nextern int thermal_perf_get_mode(void);\n"
    if "thermal_perf_get_fastcharge" not in content:
        content = fc_decl + content

    if "tp_override_val" in content:
        print("✓ power_supply_core.c already hooked")
        return

    hook_code = """
	union power_supply_propval tp_override_val;
	if (thermal_perf_get_fastcharge() == 1 || thermal_perf_get_mode() == 2) {
		if (psp == POWER_SUPPLY_PROP_CHARGE_CONTROL_LIMIT) {
			tp_override_val.intval = 0;
			val = &tp_override_val;
		}
	}
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
    print(f"::warning::Could not match cpufreq_set_policy CPUFREQ_ADJUST in {filepath}")

if __name__ == "__main__":
    common_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    patch_cpufreq_cooling(os.path.join(common_dir, "drivers/thermal/cpufreq_cooling.c"))
    patch_devfreq_cooling(os.path.join(common_dir, "drivers/thermal/devfreq_cooling.c"))
    patch_thermal_sysfs(os.path.join(common_dir, "drivers/thermal/thermal_sysfs.c"))
    patch_power_supply_core(os.path.join(common_dir, "drivers/power/supply/power_supply_core.c"))
    patch_cpufreq_core(os.path.join(common_dir, "drivers/cpufreq/cpufreq.c"))
