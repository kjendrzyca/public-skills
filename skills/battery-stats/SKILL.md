---
name: battery-stats
description: Check macOS laptop battery telemetry, current power drain, average watt usage, battery health, cycle count, and recent real-world battery runtime from local pmset/ioreg/system_profiler data. Use when the user asks about current Mac power drain, wattage, average power draw, battery health, "battery report", battery life, average runtime, or how long their Mac battery lasts.
license: MIT
---

# Battery Stats

Use this skill to answer battery-status questions directly from the local Mac. Do not ask the user to run commands unless they explicitly want the commands.

## Quick Start

Run the bundled script from this skill directory:

```bash
python3 scripts/battery-stats.py
```

Use JSON when another tool or follow-up calculation needs structured data:

```bash
python3 scripts/battery-stats.py --json
```

## Workflow

1. Confirm the current machine is macOS. If `pmset`, `ioreg`, or `system_profiler` is missing, report that the skill only supports macOS battery telemetry.
2. Run `scripts/battery-stats.py`.
3. Read the `Current Battery` section first:
   - `current_drain_w` is the current whole-battery drain in watts, computed from battery voltage and amperage.
   - `battery_power_telemetry_w` is the battery telemetry rail when available. Treat it as secondary because it can diverge from the direct voltage/current reading.
   - These values are instantaneous and can move quickly with CPU, display brightness, network, browser, and background work.
4. Read the `Health` section:
   - Prefer health calculated from nominal capacity divided by design capacity.
   - Include cycle count and macOS condition when available.
5. Read the `Runtime Estimate` section:
   - Prefer the human `Screen-on weighted full runtime` line, or `runtime.screen_on_robust.weighted_full_runtime` in JSON, for "how long does the battery last during use?"
   - Treat the human `Wall-clock battery runtime including sleep` line, or `runtime.wall_clock_usable.weighted_full_runtime` in JSON, as standby-inclusive context because it includes sleep and maintenance wakes.
   - If the current discharge session is included, call it provisional.
6. Read the `Power Usage Estimate` section:
   - Use `Average screen-on draw`, or `screen_on_robust.weighted_avg_power_w` in JSON, as the best single number for typical watts during real screen-on use.
   - Use `Median session draw` and `Typical range (25-75%)` to describe normal variation.
   - Use `Heavier sessions (90%)` and `Session draw range` to describe heavier workloads without overreacting to one noisy session.
   - Prefer the longer stored history when available; otherwise use the regular `pmset` history.
7. Answer with concrete numbers and a short interpretation. Include the log span so the user knows what period the average covers.

## Interpretation Rules

- macOS does not provide a Windows-style generated `batteryreport`; the useful local sources are `pmset -g batt`, `ioreg -rn AppleSmartBattery -r`, `system_profiler SPPowerDataType`, and `pmset -g log`.
- Do not overstate precision. Report current drain to about one decimal watt and runtime to the nearest 5-15 minutes.
- When current macOS "time remaining" and wattage-derived projections differ, explain that both are estimates and current drain changes second by second.
- Explain average watt usage as an estimate derived from observed battery-percent drop, elapsed screen-on time, and current usable battery energy in Wh. It is useful for describing the user's real workflow, not for hardware benchmarking.
- A good wording pattern is: "During real screen-on use, this Mac averages about X W. Normal sessions are roughly A-B W, heavier sessions are around C W, and that lines up with about Y hours of practical runtime."
- Do not include battery serial numbers or other hardware identifiers unless the user explicitly asks for them.
- If recent history has too few meaningful discharge sessions, say that the average is not reliable and fall back to the current macOS estimate plus health and drain.
