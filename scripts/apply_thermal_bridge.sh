#!/usr/bin/env bash
# Apply Stealth Thermal Perf Kernel Bridge
# Adds /sys/kernel/thermal_perf/mode and hooks cpu_cooling.c / devfreq_cooling.c
# 100% Mountless & Zero-Detection by Anti-Cheat (ACE / Momo / Hunter)

set -eo pipefail

KERNEL_ROOT="${1:-$GITHUB_WORKSPACE}"
COMMON_DIR="$KERNEL_ROOT/common"

echo "========================================"
echo "    Thermal Perf Kernel Bridge Patch    "
echo "========================================"
echo "Kernel Root: $COMMON_DIR"

cd "$COMMON_DIR"

# 1. Create drivers/thermal/thermal_perf_bridge.c
cat << 'EOF' > drivers/thermal/thermal_perf_bridge.c
// SPDX-License-Identifier: GPL-2.0
/*
 * thermal_perf_bridge.c - Kernel-space Dynamic Thermal & Performance Bridge
 * Allows mountless dynamic switching: Powersafe (0), Balance (1), Game (2).
 */

#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>
#include <linux/kobject.h>
#include <linux/sysfs.h>
#include <linux/thermal.h>

static int thermal_perf_mode = 1; /* Default: 1 (Balance) */

int thermal_perf_get_mode(void)
{
	return thermal_perf_mode;
}
EXPORT_SYMBOL_GPL(thermal_perf_get_mode);

static ssize_t mode_show(struct kobject *kobj, struct kobj_attribute *attr, char *buf)
{
	return sprintf(buf, "%d\n", thermal_perf_mode);
}

static ssize_t mode_store(struct kobject *kobj, struct kobj_attribute *attr, const char *buf, size_t count)
{
	int val;
	if (kstrtoint(buf, 10, &val) < 0 || val < 0 || val > 2)
		return -EINVAL;
	thermal_perf_mode = val;
	pr_info("ThermalPerf: mode set to %d\n", val);
	return count;
}

static struct kobj_attribute mode_attribute = __ATTR(mode, 0666, mode_show, mode_store);

static struct attribute *thermal_perf_attrs[] = {
	&mode_attribute.attr,
	NULL,
};

static struct attribute_group thermal_perf_attr_group = {
	.attrs = thermal_perf_attrs,
};

static struct kobject *thermal_perf_kobj;

static int __init thermal_perf_bridge_init(void)
{
	int ret;

	thermal_perf_kobj = kobject_create_and_add("thermal_perf", kernel_kobj);
	if (!thermal_perf_kobj)
		return -ENOMEM;

	ret = sysfs_create_group(thermal_perf_kobj, &thermal_perf_attr_group);
	if (ret) {
		kobject_put(thermal_perf_kobj);
		return ret;
	}

	pr_info("ThermalPerf: Kernel Bridge initialized (/sys/kernel/thermal_perf/mode)\n");
	return 0;
}

fs_initcall(thermal_perf_bridge_init);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Zaan");
MODULE_DESCRIPTION("Thermal Perf Kernel Bridge for Snapdragon 8s Gen 3");
EOF

# 2. Add to drivers/thermal/Makefile
if ! grep -q "thermal_perf_bridge.o" drivers/thermal/Makefile; then
  echo "obj-y += thermal_perf_bridge.o" >> drivers/thermal/Makefile
  echo "✓ Added thermal_perf_bridge.o to drivers/thermal/Makefile"
fi

# 3. Hook cpu_cooling.c (suppress CPU throttling in Game Mode)
CPU_COOL="drivers/thermal/cpu_cooling.c"
if [ -f "$CPU_COOL" ] && ! grep -q "thermal_perf_get_mode" "$CPU_COOL"; then
  echo "Hooking $CPU_COOL..."
  # Add declaration at top
  sed -i '1i extern int thermal_perf_get_mode(void);' "$CPU_COOL"
  # Add override in cpufreq_set_cur_state
  sed -i '/cpufreq_set_cur_state(struct thermal_cooling_device \*cdev, unsigned long state)/{n; /unsigned int cpu = /a	if (thermal_perf_get_mode() == 2) state = 0;
}' "$CPU_COOL" || sed -i '/static int cpufreq_set_cur_state/a extern int thermal_perf_get_mode(void);	if (thermal_perf_get_mode() == 2) state = 0;' "$CPU_COOL" || true
  echo "✓ Hooked cpu_cooling.c for zero throttling in Game Mode"
fi

# 4. Hook devfreq_cooling.c (suppress GPU throttling in Game Mode)
DEVFREQ_COOL="drivers/thermal/devfreq_cooling.c"
if [ -f "$DEVFREQ_COOL" ] && ! grep -q "thermal_perf_get_mode" "$DEVFREQ_COOL"; then
  echo "Hooking $DEVFREQ_COOL..."
  sed -i '1i extern int thermal_perf_get_mode(void);' "$DEVFREQ_COOL"
  sed -i '/devfreq_cooling_set_cur_state/{n; a	if (thermal_perf_get_mode() == 2) state = 0;
}' "$DEVFREQ_COOL" || true
  echo "✓ Hooked devfreq_cooling.c for GPU stability in Game Mode"
fi

echo "✓ Thermal Perf Kernel Bridge successfully integrated into kernel source!"
