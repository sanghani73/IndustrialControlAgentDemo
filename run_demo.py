"""
Demo orchestrator — starts all agents and the Flask dashboard.

Usage:
    python run_demo.py

This launches:
  - Flask dashboard on port 5001
  - Agent 3 (Alarm Correlator) — Change Stream on plant_alarms
  - Agent 1 (Reactive SOP Matcher) — Change Stream on correlated_alarm_groups
  - Agent 2 (Trend Analysis) — Periodic polling on sensor_telemetry
  - Agent 4 (Production Monitor) — Periodic polling on production_plans

Then run scenarios in a separate terminal:
    python -m simulate.simulate_scenario --scenario scn-01
"""

import subprocess
import sys
import signal
import os
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PROCESSES = []


def start_process(name, module):
    print(f"  Starting {name}...")
    proc = subprocess.Popen(
        [sys.executable, "-m", module],
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    PROCESSES.append((name, proc))
    return proc


def stream_output(name, proc):
    import threading

    def _read():
        for line in proc.stdout:
            print(f"[{name}] {line}", end="")

    t = threading.Thread(target=_read, daemon=True)
    t.start()


def shutdown(signum=None, frame=None):
    print("\n\nShutting down all processes...")
    for name, proc in PROCESSES:
        if proc.poll() is None:
            print(f"  Stopping {name}...")
            proc.terminate()
    for name, proc in PROCESSES:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    print("All processes stopped.")
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print("=" * 60)
    print("  Autonomous Industrial Control Agent — Demo Runner")
    print("=" * 60)
    print()

    print("[1/5] Starting Flask Dashboard...")
    dashboard = start_process("Dashboard", "dashboard.app")
    stream_output("Dashboard", dashboard)
    time.sleep(1)

    print("[2/5] Starting Agent 3 (Alarm Correlator)...")
    correlator = start_process("Correlator", "agents.agent_correlator")
    stream_output("Correlator", correlator)

    print("[3/5] Starting Agent 1 (Reactive SOP Matcher)...")
    reactive = start_process("Reactive", "agents.agent_reactive")
    stream_output("Reactive", reactive)

    print("[4/5] Starting Agent 2 (Trend Analysis)...")
    trend = start_process("Trend", "agents.agent_trend")
    stream_output("Trend", trend)

    print("[5/5] Starting Agent 4 (Production Monitor)...")
    production = start_process("Production", "agents.agent_production")
    stream_output("Production", production)

    print()
    print("=" * 60)
    print("  All agents running. Dashboard at http://localhost:5001")
    print()
    print("  To trigger a scenario, open a new terminal and run:")
    print("    python -m simulate.simulate_scenario --scenario scn-01")
    print()
    print("  Press Ctrl+C to stop all processes.")
    print("=" * 60)
    print()

    while True:
        for name, proc in PROCESSES:
            if proc.poll() is not None:
                print(f"\n[WARNING] {name} exited with code {proc.returncode}")
        time.sleep(2)


if __name__ == "__main__":
    main()
