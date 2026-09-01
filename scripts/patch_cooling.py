#!/usr/bin/env python3
import os
import sys
import re

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

    # Linux 6.1+ pattern
    needle_6_1 = "if (state > cpufreq_cdev->max_level)"
    if needle_6_1 in content:
        idx = content.find(needle_6_1)
        line_start = content.rfind("\n", 0, idx) + 1
        content = content[:line_start] + "\tthermal_perf_filter_cdev_state(cdev->type, &state);\n\n" + content[line_start:]
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print("✓ Hooked cpufreq_cooling.c (Universal CPU Cooling Hook)")
        return

    # Fallback pattern
    needle_old = "target_freq = cpufreq_cdev->freq_table[state].frequency"
    if needle_old in content:
        idx = content.find(needle_old)
        line_start = content.rfind("\n", 0, idx) + 1
        content = content[:line_start] + "\tthermal_perf_filter_cdev_state(cdev->type, &state);\n" + content[line_start:]
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print("✓ Hooked cpufreq_cooling.c (Legacy Function Hook)")
        return

    print(f"::warning::Could not match cpufreq_cooling hook point in {filepath}")

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

    # Linux 6.1+ pattern
    needle_6_1 = "if (state == dfc->cooling_state)"
    if needle_6_1 in content:
        idx = content.find(needle_6_1)
        line_start = content.rfind("\n", 0, idx) + 1
        content = content[:line_start] + "\tthermal_perf_filter_cdev_state(cdev->type, &state);\n\n" + content[line_start:]
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print("✓ Hooked devfreq_cooling.c (Universal GPU Devfreq Hook)")
        return

    # Fallback pattern
    needle_old = "freq = dfc->freq_table[state]"
    if needle_old in content:
        idx = content.find(needle_old)
        line_start = content.rfind("\n", 0, idx) + 1
        content = content[:line_start] + "\tthermal_perf_filter_cdev_state(cdev->type, &state);\n" + content[line_start:]
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print("✓ Hooked devfreq_cooling.c (Legacy GPU Devfreq Hook)")
        return

    print(f"::warning::Could not match devfreq_cooling hook point in {filepath}")

def patch_thermal_sysfs(filepath):
    if not os.path.exists(filepath):
        print(f"::warning::{filepath} not found")
        return
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # 1. Dynamic Game Mode Temperature Spoof (Only active in Mode 2, Mode 1/Balance is 100% stock)
    if "tp_mode == 2" not in content:
        match_temp = re.search(r"\n(?:static\s+ssize_t\s+)?temp_show\s*\([^{]+\{", content)
        if match_temp:
            fn_start = match_temp.end()
            depth = 1
            fn_end = fn_start
            while depth > 0 and fn_end < len(content):
                if content[fn_end] == '{':
                    depth += 1
                elif content[fn_end] == '}':
                    depth -= 1
                fn_end += 1
            
            fn_body = content[fn_start:fn_end]
            ret_match = re.search(r"(\n\s*return\s+(?:sprintf|sysfs_emit)\s*\(buf[^\n]+)", fn_body)
            if ret_match:
                insert_pos = fn_start + ret_match.start()
                temp_hook = """
\t{
\t\textern int thermal_perf_get_mode(void);
\t\tint tp_mode = thermal_perf_get_mode();
\t\tif (tp_mode == 2) {
\t\t\tif (strstr(tz->type, "cpu") || strstr(tz->type, "gpu") ||
\t\t\t    strstr(tz->type, "aoss") || strstr(tz->type, "quiet") ||
\t\t\t    strstr(tz->type, "thermal") || strstr(tz->type, "soc") ||
\t\t\t    strstr(tz->type, "cpuss") || strstr(tz->type, "gpuss") ||
\t\t\t    strstr(tz->type, "nsphvx") || strstr(tz->type, "nsphmx") ||
\t\t\t    strstr(tz->type, "ddr") || strstr(tz->type, "video") ||
\t\t\t    strstr(tz->type, "camera")) {
\t\t\t\treturn sprintf(buf, "%d\\n", 29000); /* 29.0°C in Game Mode */
\t\t\t}
\t\t}
\t}
"""
                content = content[:insert_pos] + temp_hook + content[insert_pos:]
                print("✓ Hooked thermal_sysfs.c (Dynamic Game-Only Temp Spoof)")
            else:
                print(f"::warning::Could not match return sprintf in temp_show of {filepath}")
        else:
            print(f"::warning::Could not match temp_show in {filepath}")

    # 2. Hook cur_state_store (Cooling device filter)
    if "thermal_perf_filter_cdev_state(cdev->type, &state)" not in content:
        match_cdev = re.search(r"\n(?:static\s+ssize_t\s+)?cur_state_store\s*\(", content)
        if match_cdev:
            fn_idx = match_cdev.start()
            mutex_needle = "mutex_lock(&cdev->lock);"
            m_idx = content.find(mutex_needle, fn_idx)
            if m_idx != -1:
                semi_idx = m_idx + len(mutex_needle)
                cdev_hook = "\n\t{\n\t\textern void thermal_perf_filter_cdev_state(const char *type, unsigned long *state);\n\t\tthermal_perf_filter_cdev_state(cdev->type, &state);\n\t}"
                content = content[:semi_idx] + cdev_hook + content[semi_idx:]
                print("✓ Hooked thermal_sysfs.c (Userspace Cooling Device Sysfs Write Hook)")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

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

def patch_power_supply_sysfs(filepath):
    if not os.path.exists(filepath):
        print(f"::warning::{filepath} not found")
        return
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    if "POWER_SUPPLY_PROP_TEMP" in content and "thermal_perf_get_mode" not in content:
        match_fn = re.search(r"\n(?:static\s+ssize_t\s+)?power_supply_show_property\s*\([^{]+\{", content)
        if match_fn:
            fn_start = match_fn.end()
            depth = 1
            fn_end = fn_start
            while depth > 0 and fn_end < len(content):
                if content[fn_end] == '{':
                    depth += 1
                elif content[fn_end] == '}':
                    depth -= 1
                fn_end += 1

            fn_body = content[fn_start:fn_end]
            ret_match = re.search(r"(\n\s*return\s+(?:sprintf|sysfs_emit)\s*\(buf[^\n]+)", fn_body)
            if ret_match:
                insert_pos = fn_start + ret_match.start()
                psy_hook = """
\t{
\t\textern int thermal_perf_get_mode(void);
\t\tif (thermal_perf_get_mode() == 2) {
\t\t\tif (off == POWER_SUPPLY_PROP_TEMP || off == POWER_SUPPLY_PROP_TEMP_AMBIENT) {
\t\t\t\treturn sprintf(buf, "%d\\n", 290); /* 29.0°C in Game Mode */
\t\t\t}
\t\t}
\t}
"""
                content = content[:insert_pos] + psy_hook + content[insert_pos:]
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                print("✓ Hooked power_supply_sysfs.c (Dynamic Battery Temp Spoof 29.0°C)")
                return

    print(f"::warning::Could not patch {filepath}")

if __name__ == "__main__":
    common_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    patch_cpufreq_cooling(os.path.join(common_dir, "drivers/thermal/cpufreq_cooling.c"))
    patch_devfreq_cooling(os.path.join(common_dir, "drivers/thermal/devfreq_cooling.c"))
    patch_thermal_sysfs(os.path.join(common_dir, "drivers/thermal/thermal_sysfs.c"))
    patch_cpufreq_core(os.path.join(common_dir, "drivers/cpufreq/cpufreq.c"))
    patch_power_supply_sysfs(os.path.join(common_dir, "drivers/power/supply/power_supply_sysfs.c"))
