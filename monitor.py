#!/usr/bin/env python3
"""
GitHub Actions Workflow Run Monitor
Real-time progress and error monitor for Alfnnnnyy/GKI_KernelSU_SUSFS.
"""

import sys
import os
import time
import json
import subprocess
import urllib.request
import urllib.error

REPO = "Alfnnnnyy/GKI_KernelSU_SUSFS"

# ANSI Color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

def get_token():
    # 1. Check GITHUB_TOKEN or GH_TOKEN
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token
    # 2. Try gh auth token CLI
    try:
        res = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True)
        t = res.stdout.strip()
        if t:
            return t
    except Exception:
        pass
    # 3. Fallback to ~/.config/gh/hosts.yml
    hosts_path = os.path.expanduser("~/.config/gh/hosts.yml")
    if os.path.exists(hosts_path):
        try:
            import yaml
            with open(hosts_path) as f:
                cfg = yaml.safe_load(f)
                return cfg.get("github.com", {}).get("oauth_token", "")
        except Exception:
            pass
    return ""

def api_get(endpoint, token):
    url = f"https://api.github.com/repos/{REPO}/{endpoint}"
    headers = {
        "User-Agent": "actions-monitor",
        "Accept": "application/vnd.github.v3+json",
    }
    if token:
        headers["Authorization"] = f"token {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())

def get_latest_run(token):
    data = api_get("actions/runs?per_page=5", token)
    runs = data.get("workflow_runs", [])
    if not runs:
        return None
    # Prefer in_progress or queued runs, otherwise most recent
    active = [r for r in runs if r.get("status") in ("in_progress", "queued")]
    if active:
        return active[0]
    return runs[0]

def print_log_failed(run_id):
    print(f"\n{YELLOW}{BOLD}--- Log Kegagalan (gh run view --log-failed) ---{RESET}")
    try:
        res = subprocess.run(
            ["gh", "run", "view", str(run_id), "--log-failed"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if res.stdout:
            print(res.stdout[-4000:])
        elif res.stderr:
            print(f"{DIM}{res.stderr.strip()}{RESET}")
    except Exception as e:
        print(f"{DIM}Gagal mengambil log: {e}{RESET}")

def main():
    token = get_token()
    
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        run_id = int(sys.argv[1])
        print(f"{CYAN}{BOLD}▶ Memantau Run ID spesifik:{RESET} #{run_id}")
    else:
        print(f"{CYAN}Mencari workflow run terbaru di {REPO}...{RESET}")
        latest = get_latest_run(token)
        if not latest:
            print(f"{RED}Tidak ada workflow run yang ditemukan di {REPO}.{RESET}")
            sys.exit(1)
        run_id = latest["id"]
        branch = latest.get("head_branch", "unknown")
        wf_name = latest.get("name", "workflow")
        status = latest.get("status", "unknown")
        print(f"{CYAN}{BOLD}▶ Memantau Run ID #{run_id}{RESET} [{wf_name} @ {branch}] (Status: {status})")

    print(f"{DIM}URL: https://github.com/{REPO}/actions/runs/{run_id}{RESET}\n")

    seen_failed_jobs = set()

    while True:
        try:
            # 1. Fetch overall run status
            run_data = api_get(f"actions/runs/{run_id}", token)
            run_status = run_data.get("status")
            run_conclusion = run_data.get("conclusion")

            # 2. Fetch jobs
            jobs_data = api_get(f"actions/runs/{run_id}/jobs?per_page=100", token)
            jobs = jobs_data.get("jobs", [])

            total = len(jobs)
            completed = [j for j in jobs if j.get("status") == "completed"]
            successful = [j for j in completed if j.get("conclusion") == "success"]
            failed = [j for j in jobs if j.get("conclusion") == "failure"]
            in_progress = [j for j in jobs if j.get("status") == "in_progress"]
            queued = [j for j in jobs if j.get("status") == "queued"]

            ts = time.strftime("%H:%M:%S")

            status_line = (
                f"[{ts}] Total: {BOLD}{total}{RESET} | "
                f"Selesai: {GREEN}{len(successful)}✓{RESET} | "
                f"Gagal: {RED}{len(failed)}✗{RESET} | "
                f"Berjalan: {YELLOW}{len(in_progress)}▶{RESET} | "
                f"Antrean: {DIM}{len(queued)}⏳{RESET}"
            )
            print(status_line, flush=True)

            # Check new failed jobs
            for fj in failed:
                jid = fj.get("id")
                if jid not in seen_failed_jobs:
                    seen_failed_jobs.add(jid)
                    jname = fj.get("name", "Unknown Job")
                    print(f"\n{RED}{BOLD}🚨 JOB GAGAL DETEKSI: {jname} (ID: {jid}){RESET}", flush=True)
                    for step in fj.get("steps", []):
                        if step.get("conclusion") == "failure":
                            sname = step.get("name")
                            snum = step.get("number")
                            print(f"   {RED}↳ Step #{snum} Gagal: {BOLD}{sname}{RESET}", flush=True)

            # Termination conditions
            if run_status == "completed":
                if run_conclusion == "success":
                    print(f"\n{GREEN}{BOLD}🎉 Semua build & release workflow selesai dengan SUKSES!{RESET}")
                    sys.exit(0)
                elif run_conclusion == "failure":
                    print(f"\n{RED}{BOLD}❌ Workflow Run #{run_id} berakhir dengan STATUS GAGAL (conclusion: failure).{RESET}")
                    print_log_failed(run_id)
                    sys.exit(1)
                elif run_conclusion == "cancelled":
                    print(f"\n{YELLOW}{BOLD}⚠️ Workflow Run #{run_id} telah DIBATALKAN.{RESET}")
                    sys.exit(2)
                else:
                    print(f"\n{DIM}Workflow selesai dengan status: {run_conclusion}{RESET}")
                    sys.exit(0)

        except urllib.error.HTTPError as he:
            print(f"{RED}[HTTP Error {he.code}] {he.reason}{RESET}", flush=True)
        except Exception as e:
            print(f"{DIM}[Error] {e}{RESET}", flush=True)

        time.sleep(8)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Pemantauan dihentikan oleh pengguna.{RESET}")
        sys.exit(0)
