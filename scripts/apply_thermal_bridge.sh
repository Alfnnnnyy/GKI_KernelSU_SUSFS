#!/usr/bin/env bash
# Apply Stealth Thermal Perf Kernel Bridge
# Adds /sys/kernel/thermal_perf/mode & /sys/kernel/thermal_perf/fastcharge
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
 * thermal_perf_bridge.c - Pure Ring-0 Kernel Actuator & Performance Bridge
 * 100% Stealth & Mountless: Handles CPU Policy Caps, Cooling Interception,
 * and 90W Fast Charging directly in-memory without userspace sysfs tampering.
 */

#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>
#include <linux/kobject.h>
#include <linux/sysfs.h>
#include <linux/thermal.h>
#include <linux/string.h>
#include <linux/cpufreq.h>

static int thermal_perf_mode = 1;       /* Default: 1 (Balance) */
static int thermal_perf_fastcharge = 0; /* Default: 0 (Normal charging) */

int thermal_perf_get_mode(void)
{
	return thermal_perf_mode;
}
EXPORT_SYMBOL_GPL(thermal_perf_get_mode);

int thermal_perf_get_fastcharge(void)
{
	return thermal_perf_fastcharge;
}
EXPORT_SYMBOL_GPL(thermal_perf_get_fastcharge);

void thermal_perf_filter_cdev_state(const char *type, unsigned long *state)
{
	int mode = thermal_perf_mode;
	int fc = thermal_perf_fastcharge;

	if (!type || !state)
		return;

	/* 1. Fastcharge or Game Mode: Neutralize all battery/charger thermal throttling */
	if (fc == 1 || mode == 2) {
		if (strstr(type, "battery") || strstr(type, "chg") || 
		    strstr(type, "charger") || strstr(type, "fcc") ||
		    strstr(type, "thermal_fcc") || strstr(type, "usb")) {
			*state = 0; /* Force State 0: 100% Full Peak Charging Current */
			return;
		}
	}

	/* 2. Game Mode: Neutralize CPU, GPU, DDR, Cluster, Pause, and Hotplug throttling */
	if (mode == 2) {
		if (strstr(type, "cpu") || strstr(type, "gpu") || 
		    strstr(type, "kgsl") || strstr(type, "ddr") || 
		    strstr(type, "cluster") || strstr(type, "pause") || 
		    strstr(type, "hotplug") || strstr(type, "cdev")) {
			*state = 0; /* Force State 0: 100% Zero Throttle, Max Clock (3.01 GHz) */
			return;
		}
	}
}
EXPORT_SYMBOL_GPL(thermal_perf_filter_cdev_state);

static void thermal_perf_apply_kernel_mode(int mode)
{
	int cpu;
	struct cpufreq_policy *policy;

	for_each_possible_cpu(cpu) {
		policy = cpufreq_cpu_get(cpu);
		if (!policy)
			continue;

		if (policy->cpu == cpu) {
			if (mode == 2) {
				/* Game Mode: Restore policy max to hardware stock maximum */
				policy->max = policy->cpuinfo.max_freq;
			} else if (mode == 0) {
				/* Powersafe Mode: Cap maximum frequency to 70% of hardware max */
				policy->max = (policy->cpuinfo.max_freq * 70) / 100;
			} else {
				/* Balance Mode: Restore stock */
				policy->max = policy->cpuinfo.max_freq;
			}
			cpufreq_update_policy(cpu);
		}
		cpufreq_cpu_put(policy);
	}
}

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
	thermal_perf_apply_kernel_mode(val);
	pr_info("ThermalPerf: Ring-0 mode set to %d\n", val);
	return count;
}

static ssize_t fastcharge_show(struct kobject *kobj, struct kobj_attribute *attr, char *buf)
{
	return sprintf(buf, "%d\n", thermal_perf_fastcharge);
}

static ssize_t fastcharge_store(struct kobject *kobj, struct kobj_attribute *attr, const char *buf, size_t count)
{
	int val;
	if (kstrtoint(buf, 10, &val) < 0 || (val != 0 && val != 1))
		return -EINVAL;
	thermal_perf_fastcharge = val;
	pr_info("ThermalPerf: Ring-0 90W fastcharge set to %d\n", val);
	return count;
}

static struct kobj_attribute mode_attribute = __ATTR(mode, 0644, mode_show, mode_store);
static struct kobj_attribute fastcharge_attribute = __ATTR(fastcharge, 0644, fastcharge_show, fastcharge_store);

static struct attribute *thermal_perf_attrs[] = {
	&mode_attribute.attr,
	&fastcharge_attribute.attr,
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

	pr_info("ThermalPerf: Ring-0 Kernel Bridge initialized (/sys/kernel/thermal_perf/{mode,fastcharge})\n");
	return 0;
}

fs_initcall(thermal_perf_bridge_init);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Zaan");
MODULE_DESCRIPTION("Thermal Perf Pure Ring-0 Kernel Actuator");
EOF

# 2. Add to drivers/thermal/Makefile
if ! grep -q "thermal_perf_bridge.o" drivers/thermal/Makefile; then
  echo "obj-y += thermal_perf_bridge.o" >> drivers/thermal/Makefile
  echo "✓ Added thermal_perf_bridge.o to drivers/thermal/Makefile"
fi

# 3. Hook thermal cooling devices & PMIC power supply using patch_cooling.py
python3 "$GITHUB_WORKSPACE/scripts/patch_cooling.py" "$COMMON_DIR"

echo "✓ Thermal Perf Kernel Bridge successfully integrated into kernel source!"
