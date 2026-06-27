#!/usr/bin/env python3
"""Report macOS battery drain, health, and recent runtime from local telemetry."""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import statistics
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any


LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [+-]\d{4})\s+(.+?)\s{2,}(.*)$"
)
SOURCE_RE = re.compile(r"Using\s+(BATT|Batt|AC)\s*\(?Charge:\s*(\d+)%?\)?", re.I)
SYSLOG_LINE_RE = re.compile(
    r"^([A-Z][a-z]{2})\s+(\d+)\s+(\d\d:\d\d:\d\d)\s+\S+\s+powerd\[\d+\]\s+<[^>]+>:\s+(.*)$"
)
MONTHS = {
    name: index
    for index, name in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        1,
    )
}


def run_command(args: list[str], timeout: int = 30) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            args,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        return 127, "", str(exc)
    except subprocess.TimeoutExpired as exc:
        return 124, exc.stdout or "", exc.stderr or f"timed out after {timeout}s"
    return result.returncode, result.stdout, result.stderr


def signed_uint64(value: int | None) -> int | None:
    if value is None:
        return None
    if value >= 2**63:
        return value - 2**64
    return value


def raw_int(text: str, key: str) -> int | None:
    match = re.search(rf'"{re.escape(key)}"\s*=\s*(\d+)', text)
    return int(match.group(1)) if match else None


def format_duration(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    seconds = max(0, int(round(seconds)))
    hours, rem = divmod(seconds, 3600)
    minutes, _ = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


def percentile(values: list[float], percent: float) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    index = (len(sorted_values) - 1) * percent / 100
    floor_index = math.floor(index)
    ceil_index = math.ceil(index)
    if floor_index == ceil_index:
        return sorted_values[int(index)]
    lower = sorted_values[floor_index] * (ceil_index - index)
    upper = sorted_values[ceil_index] * (index - floor_index)
    return lower + upper


def parse_pmset_batt(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {"raw": text.strip()}
    source = re.search(r"Now drawing from '([^']+)'", text)
    if source:
        data["power_source"] = source.group(1)

    battery_line = next((line.strip() for line in text.splitlines() if "%" in line), "")
    data["battery_line"] = battery_line

    percent = re.search(r"(\d+)%;", battery_line)
    if percent:
        data["charge_percent"] = int(percent.group(1))

    status = re.search(r"\d+%;\s*([^;]+);", battery_line)
    if status:
        data["status"] = status.group(1).strip()

    remaining = re.search(r"(\d+:\d+)\s+remaining", battery_line)
    if remaining:
        data["time_remaining"] = remaining.group(1)
    elif "no estimate" in battery_line.lower():
        data["time_remaining"] = "no estimate"

    return data


def parse_ioreg_battery(text: str) -> dict[str, Any]:
    voltage_mv = raw_int(text, "AppleRawBatteryVoltage") or raw_int(text, "Voltage")
    amperage_ma = signed_uint64(raw_int(text, "InstantAmperage") or raw_int(text, "Amperage"))
    battery_power_mw = signed_uint64(raw_int(text, "BatteryPower"))

    current_capacity_mah = raw_int(text, "AppleRawCurrentCapacity")
    max_capacity_mah = raw_int(text, "AppleRawMaxCapacity")
    nominal_capacity_mah = raw_int(text, "NominalChargeCapacity")
    design_capacity_mah = raw_int(text, "DesignCapacity")
    cycle_count = raw_int(text, "CycleCount")
    avg_time_to_empty_min = raw_int(text, "AvgTimeToEmpty")
    time_remaining_min = raw_int(text, "TimeRemaining")
    temperature_raw = raw_int(text, "Temperature")

    drain_by_vi_w = None
    if voltage_mv is not None and amperage_ma is not None:
        drain_by_vi_w = abs(voltage_mv * amperage_ma) / 1_000_000

    battery_power_w = None
    if battery_power_mw is not None:
        battery_power_w = abs(battery_power_mw) / 1000

    raw_charge_percent = None
    if current_capacity_mah and max_capacity_mah:
        raw_charge_percent = current_capacity_mah / max_capacity_mah * 100

    health_percent = None
    if nominal_capacity_mah and design_capacity_mah:
        health_percent = nominal_capacity_mah / design_capacity_mah * 100

    usable_energy_wh_estimate = None
    if nominal_capacity_mah and voltage_mv:
        usable_energy_wh_estimate = nominal_capacity_mah * voltage_mv / 1_000_000

    temperature_c = None
    if temperature_raw:
        temperature_c = temperature_raw / 10 - 273.15

    return {
        "voltage_mv": voltage_mv,
        "amperage_ma": amperage_ma,
        "current_drain_w": drain_by_vi_w,
        "drain_by_voltage_current_w": drain_by_vi_w,
        "battery_power_telemetry_w": battery_power_w,
        "current_capacity_mah": current_capacity_mah,
        "max_capacity_mah": max_capacity_mah,
        "raw_charge_percent": raw_charge_percent,
        "nominal_capacity_mah": nominal_capacity_mah,
        "design_capacity_mah": design_capacity_mah,
        "usable_energy_wh_estimate": usable_energy_wh_estimate,
        "health_percent": health_percent,
        "cycle_count": cycle_count,
        "avg_time_to_empty_min": avg_time_to_empty_min if avg_time_to_empty_min != 65535 else None,
        "time_remaining_min": time_remaining_min if time_remaining_min != 65535 else None,
        "temperature_c": temperature_c,
    }


def parse_system_profiler(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    condition = re.search(r"Condition:\s*(.+)", text)
    if condition:
        data["condition"] = condition.group(1).strip()
    maximum_capacity = re.search(r"Maximum Capacity:\s*(\d+)%", text)
    if maximum_capacity:
        data["maximum_capacity_percent"] = int(maximum_capacity.group(1))
    cycle_count = re.search(r"Cycle Count:\s*(\d+)", text)
    if cycle_count:
        data["cycle_count"] = int(cycle_count.group(1))
    return data


@dataclass
class Session:
    start: datetime
    start_charge: int
    end: datetime
    end_charge: int
    duration_s: float
    drop_pct: int
    end_reason: str

    @property
    def projected_full_runtime_s(self) -> float | None:
        if self.drop_pct <= 0:
            return None
        return self.duration_s / self.drop_pct * 100

    def as_json(self) -> dict[str, Any]:
        return self.as_json_with_energy(None)

    def as_json_with_energy(self, usable_energy_wh: float | None) -> dict[str, Any]:
        energy_wh = None
        avg_power_w = None
        if usable_energy_wh is not None and self.drop_pct > 0:
            energy_wh = usable_energy_wh * self.drop_pct / 100
            duration_h = self.duration_s / 3600
            if duration_h > 0:
                avg_power_w = energy_wh / duration_h
        return {
            "start": self.start.isoformat(),
            "start_charge": self.start_charge,
            "end": self.end.isoformat(),
            "end_charge": self.end_charge,
            "duration_s": self.duration_s,
            "duration": format_duration(self.duration_s),
            "drop_pct": self.drop_pct,
            "energy_wh_estimate": energy_wh,
            "avg_power_w_estimate": avg_power_w,
            "projected_full_runtime_s": self.projected_full_runtime_s,
            "projected_full_runtime": format_duration(self.projected_full_runtime_s),
            "end_reason": self.end_reason,
        }


def summarize_sessions(sessions: list[Session], usable_energy_wh: float | None = None) -> dict[str, Any]:
    if not sessions:
        return {
            "session_count": 0,
            "observed_duration_s": 0,
            "observed_duration": "0m",
            "observed_drop_pct": 0,
            "estimated_energy_wh": None,
            "weighted_full_runtime_s": None,
            "weighted_full_runtime": None,
            "median_projected_full_runtime_s": None,
            "median_projected_full_runtime": None,
            "min_projected_full_runtime": None,
            "max_projected_full_runtime": None,
            "weighted_avg_power_w": None,
            "mean_session_power_w": None,
            "median_session_power_w": None,
            "min_session_power_w": None,
            "max_session_power_w": None,
            "p25_session_power_w": None,
            "p75_session_power_w": None,
            "p90_session_power_w": None,
        }

    total_duration = sum(session.duration_s for session in sessions)
    total_drop = sum(session.drop_pct for session in sessions)
    weighted = total_duration / total_drop * 100 if total_drop > 0 else None
    projections = [
        session.projected_full_runtime_s
        for session in sessions
        if session.projected_full_runtime_s is not None
    ]
    estimated_energy_wh = usable_energy_wh * total_drop / 100 if usable_energy_wh is not None else None
    total_duration_h = total_duration / 3600
    session_powers: list[float] = []
    if usable_energy_wh is not None:
        for session in sessions:
            duration_h = session.duration_s / 3600
            if duration_h > 0 and session.drop_pct > 0:
                session_powers.append((usable_energy_wh * session.drop_pct / 100) / duration_h)

    return {
        "session_count": len(sessions),
        "observed_duration_s": total_duration,
        "observed_duration": format_duration(total_duration),
        "observed_drop_pct": total_drop,
        "estimated_energy_wh": estimated_energy_wh,
        "weighted_full_runtime_s": weighted,
        "weighted_full_runtime": format_duration(weighted),
        "median_projected_full_runtime_s": statistics.median(projections) if projections else None,
        "median_projected_full_runtime": format_duration(statistics.median(projections)) if projections else None,
        "min_projected_full_runtime": format_duration(min(projections)) if projections else None,
        "max_projected_full_runtime": format_duration(max(projections)) if projections else None,
        "weighted_avg_power_w": estimated_energy_wh / total_duration_h
        if estimated_energy_wh is not None and total_duration_h > 0
        else None,
        "mean_session_power_w": statistics.mean(session_powers) if session_powers else None,
        "median_session_power_w": statistics.median(session_powers) if session_powers else None,
        "min_session_power_w": min(session_powers) if session_powers else None,
        "max_session_power_w": max(session_powers) if session_powers else None,
        "p25_session_power_w": percentile(session_powers, 25),
        "p75_session_power_w": percentile(session_powers, 75),
        "p90_session_power_w": percentile(session_powers, 90),
    }


@dataclass
class PowerEvent:
    timestamp: datetime
    domain: str
    text: str


def parse_power_events(
    events: list[PowerEvent],
    current_charge_percent: int | None,
    current_source: str | None,
    usable_energy_wh: float | None,
) -> dict[str, Any]:
    first_ts: datetime | None = None
    last_ts: datetime | None = None
    last_source: str | None = None
    last_charge: int | None = None
    display_on = False
    active: dict[str, Any] | None = None
    screen_sessions: list[Session] = []
    source_observations: list[tuple[datetime, str, int]] = []

    def start_session(t: datetime, charge: int | None) -> None:
        nonlocal active
        if active is not None:
            return
        if charge is None:
            return
        active = {"start": t, "start_charge": charge}

    def end_session(t: datetime, charge: int | None, reason: str) -> None:
        nonlocal active
        if active is None:
            return
        if charge is None:
            charge = last_charge
        if charge is None:
            active = None
            return
        duration = (t - active["start"]).total_seconds()
        drop = active["start_charge"] - charge
        screen_sessions.append(
            Session(
                start=active["start"],
                start_charge=active["start_charge"],
                end=t,
                end_charge=charge,
                duration_s=duration,
                drop_pct=drop,
                end_reason=reason,
            )
        )
        active = None

    for event in events:
        timestamp = event.timestamp
        first_ts = first_ts or timestamp
        last_ts = timestamp
        domain = event.domain.strip()
        line = event.text

        source_match = SOURCE_RE.search(line)
        source = None
        charge = None
        if source_match:
            source_raw, charge_text = source_match.groups()
            source = "AC" if source_raw.upper() == "AC" else "BATT"
            charge = int(charge_text)
            last_source = source
            last_charge = charge
            source_observations.append((timestamp, source, charge))

        if domain == "Wake":
            display_on = True
            if source == "BATT" or (source is None and last_source == "BATT"):
                start_session(timestamp, charge if charge is not None else last_charge)
            elif source == "AC":
                end_session(timestamp, charge, "wake_ac")

        if domain == "Notification" and "Display is turned on" in line:
            display_on = True
            if last_source == "BATT":
                start_session(timestamp, last_charge)
        elif domain == "Notification" and "Display is turned off" in line:
            display_on = False
            end_session(timestamp, charge, "display_off")

        if domain == "Sleep":
            display_on = False
            end_session(timestamp, charge, "sleep")

        if source_match:
            if source == "AC":
                end_session(timestamp, charge, "ac")
            elif source == "BATT" and display_on and active is None:
                start_session(timestamp, charge)

    if active is not None and last_ts and current_source == "Battery Power" and current_charge_percent is not None:
        now = datetime.now(last_ts.tzinfo) if last_ts.tzinfo else datetime.now()
        end_session(now, current_charge_percent, "current")

    usable_screen = [
        session
        for session in screen_sessions
        if session.duration_s >= 5 * 60 and session.drop_pct > 0
    ]
    robust_screen = [
        session
        for session in screen_sessions
        if session.duration_s >= 15 * 60 and session.drop_pct >= 2
    ]

    wall_sessions: list[Session] = []
    wall_active: dict[str, Any] | None = None
    for timestamp, source, charge in source_observations:
        if source == "BATT":
            if wall_active is None:
                wall_active = {
                    "start": timestamp,
                    "start_charge": charge,
                    "last": timestamp,
                    "last_charge": charge,
                }
            else:
                wall_active["last"] = timestamp
                wall_active["last_charge"] = charge
        elif wall_active is not None:
            duration = (wall_active["last"] - wall_active["start"]).total_seconds()
            drop = wall_active["start_charge"] - wall_active["last_charge"]
            wall_sessions.append(
                Session(
                    start=wall_active["start"],
                    start_charge=wall_active["start_charge"],
                    end=wall_active["last"],
                    end_charge=wall_active["last_charge"],
                    duration_s=duration,
                    drop_pct=drop,
                    end_reason="ac",
                )
            )
            wall_active = None

    if wall_active is not None:
        duration = (wall_active["last"] - wall_active["start"]).total_seconds()
        drop = wall_active["start_charge"] - wall_active["last_charge"]
        wall_sessions.append(
            Session(
                start=wall_active["start"],
                start_charge=wall_active["start_charge"],
                end=wall_active["last"],
                end_charge=wall_active["last_charge"],
                duration_s=duration,
                drop_pct=drop,
                end_reason="current_or_log_end",
            )
        )

    usable_wall = [
        session
        for session in wall_sessions
        if session.duration_s >= 30 * 60 and session.drop_pct > 0
    ]

    return {
        "log_span": {
            "start": first_ts.isoformat() if first_ts else None,
            "end": last_ts.isoformat() if last_ts else None,
        },
        "screen_on_usable": summarize_sessions(usable_screen, usable_energy_wh),
        "screen_on_robust": summarize_sessions(robust_screen, usable_energy_wh),
        "wall_clock_usable": summarize_sessions(usable_wall, usable_energy_wh),
        "recent_screen_sessions": [
            session.as_json_with_energy(usable_energy_wh) for session in usable_screen[-8:]
        ],
    }


def pmset_events_from_log(text: str) -> list[PowerEvent]:
    events: list[PowerEvent] = []
    for line in text.splitlines():
        match = LINE_RE.match(line)
        if not match:
            continue
        ts_text, domain, _message = match.groups()
        try:
            timestamp = datetime.strptime(ts_text, "%Y-%m-%d %H:%M:%S %z")
        except ValueError:
            continue
        events.append(PowerEvent(timestamp=timestamp, domain=domain.strip(), text=line))
    return events


def parse_pmset_log(
    text: str,
    current_charge_percent: int | None,
    current_source: str | None,
    usable_energy_wh: float | None,
) -> dict[str, Any]:
    return parse_power_events(
        pmset_events_from_log(text),
        current_charge_percent,
        current_source,
        usable_energy_wh,
    )


def domain_from_asl_message(message: str) -> str:
    if message.startswith("Summary-"):
        return "Assertions"
    if message.startswith("Wake"):
        return "Wake"
    if message.startswith("Entering Sleep state"):
        return "Sleep"
    if "Display is turned" in message:
        return "Notification"
    return "Other"


def asl_events_from_powermanagement_logs() -> tuple[list[PowerEvent], list[str]]:
    events: list[PowerEvent] = []
    errors: list[str] = []
    paths = sorted(glob.glob("/var/log/powermanagement/*.asl"))
    for path in paths:
        basename = os.path.basename(path)
        year_match = re.match(r"(\d{4})\.\d{2}\.\d{2}\.asl$", basename)
        if not year_match:
            continue
        year = int(year_match.group(1))
        code, output, err = run_command(["syslog", "-f", path], timeout=20)
        if code != 0:
            errors.append(f"syslog -f {basename} failed: {err.strip() or code}")
            continue
        for line in output.splitlines():
            match = SYSLOG_LINE_RE.match(line)
            if not match:
                continue
            month_name, day, clock, message = match.groups()
            if month_name not in MONTHS:
                continue
            try:
                hour, minute, second = [int(part) for part in clock.split(":")]
                timestamp = datetime(
                    year,
                    MONTHS[month_name],
                    int(day),
                    hour,
                    minute,
                    second,
                )
            except ValueError:
                continue
            if not (
                "Summary-" in message
                or "Display is turned" in message
                or message.startswith("Wake")
                or message.startswith("Entering Sleep state")
            ):
                continue
            events.append(
                PowerEvent(
                    timestamp=timestamp,
                    domain=domain_from_asl_message(message),
                    text=message,
                )
            )
    events.sort(key=lambda event: event.timestamp)
    return events, errors


def collect_report() -> dict[str, Any]:
    report: dict[str, Any] = {"errors": []}

    code, pmset_batt, err = run_command(["pmset", "-g", "batt"])
    if code != 0:
        report["errors"].append(f"pmset -g batt failed: {err.strip() or code}")
    report["pmset_batt"] = parse_pmset_batt(pmset_batt) if pmset_batt else {}

    code, ioreg_text, err = run_command(["ioreg", "-rn", "AppleSmartBattery", "-r"])
    if code != 0:
        report["errors"].append(f"ioreg AppleSmartBattery failed: {err.strip() or code}")
    report["smart_battery"] = parse_ioreg_battery(ioreg_text) if ioreg_text else {}
    usable_energy_wh = report["smart_battery"].get("usable_energy_wh_estimate")

    code, power_text, err = run_command(["system_profiler", "SPPowerDataType"], timeout=45)
    if code != 0:
        report["errors"].append(f"system_profiler SPPowerDataType failed: {err.strip() or code}")
    report["system_profiler"] = parse_system_profiler(power_text) if power_text else {}

    code, log_text, err = run_command(["pmset", "-g", "log"], timeout=60)
    if code != 0:
        report["errors"].append(f"pmset -g log failed: {err.strip() or code}")
        report["runtime"] = {}
    else:
        report["runtime"] = parse_pmset_log(
            log_text,
            report["pmset_batt"].get("charge_percent"),
            report["pmset_batt"].get("power_source"),
            usable_energy_wh,
        )

    long_term_events, long_term_errors = asl_events_from_powermanagement_logs()
    if long_term_errors:
        report["errors"].extend(long_term_errors)
    if long_term_events:
        report["long_term_runtime"] = parse_power_events(
            long_term_events,
            report["pmset_batt"].get("charge_percent"),
            report["pmset_batt"].get("power_source"),
            usable_energy_wh,
        )
    else:
        report["long_term_runtime"] = {}

    return report


def rounded(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def print_power_usage(summary: dict[str, Any]) -> None:
    print(f"  Average screen-on draw: {rounded(summary.get('weighted_avg_power_w'))} W")
    print(f"  Median session draw: {rounded(summary.get('median_session_power_w'))} W")
    print(
        "  Typical range (25-75%): "
        f"{rounded(summary.get('p25_session_power_w'))}-{rounded(summary.get('p75_session_power_w'))} W"
    )
    print(f"  Heavier sessions (90%): {rounded(summary.get('p90_session_power_w'))} W")
    print(
        "  Session draw range: "
        f"{rounded(summary.get('min_session_power_w'))}-{rounded(summary.get('max_session_power_w'))} W"
    )
    if summary.get("estimated_energy_wh") is not None:
        print(f"  Estimated energy used in sample: {rounded(summary.get('estimated_energy_wh'))} Wh")


def print_human(report: dict[str, Any]) -> None:
    pmset = report.get("pmset_batt", {})
    smart = report.get("smart_battery", {})
    profiler = report.get("system_profiler", {})
    runtime = report.get("runtime", {})
    long_term_runtime = report.get("long_term_runtime", {})
    robust = runtime.get("screen_on_robust", {})
    loose = runtime.get("screen_on_usable", {})
    wall = runtime.get("wall_clock_usable", {})
    long_term_robust = long_term_runtime.get("screen_on_robust", {})

    battery_power = smart.get("battery_power_telemetry_w")
    vi_power = smart.get("current_drain_w")
    preferred_drain = vi_power if vi_power is not None else battery_power

    print("Battery Stats")
    print()
    print("Current Battery")
    print(f"  Power source: {pmset.get('power_source', 'n/a')}")
    print(f"  Charge: {pmset.get('charge_percent', 'n/a')}%")
    print(f"  Status: {pmset.get('status', 'n/a')}")
    print(f"  macOS time remaining: {pmset.get('time_remaining', 'n/a')}")
    print(f"  Current drain: {rounded(preferred_drain)} W")
    print(f"  Battery telemetry drain: {rounded(battery_power)} W")
    print(f"  Voltage/current drain: {rounded(vi_power)} W")
    print(f"  Voltage: {smart.get('voltage_mv', 'n/a')} mV")
    print(f"  Current: {smart.get('amperage_ma', 'n/a')} mA")
    print()
    print("Health")
    print(f"  Condition: {profiler.get('condition', 'n/a')}")
    print(f"  Cycle count: {smart.get('cycle_count') or profiler.get('cycle_count', 'n/a')}")
    print(f"  Health by nominal/design capacity: {rounded(smart.get('health_percent'))}%")
    print(f"  macOS maximum capacity: {profiler.get('maximum_capacity_percent', 'n/a')}%")
    print(
        "  Capacity: "
        f"{smart.get('nominal_capacity_mah', 'n/a')} mAh nominal / "
        f"{smart.get('design_capacity_mah', 'n/a')} mAh design"
    )
    if smart.get("usable_energy_wh_estimate") is not None:
        print(f"  Usable energy estimate: {rounded(smart.get('usable_energy_wh_estimate'))} Wh")
    print()
    print("Runtime Estimate")
    span = runtime.get("log_span", {})
    print(f"  Log span: {span.get('start', 'n/a')} -> {span.get('end', 'n/a')}")
    print(
        "  Screen-on robust sample: "
        f"{robust.get('session_count', 0)} sessions, "
        f"{robust.get('observed_duration', '0m')} observed, "
        f"{robust.get('observed_drop_pct', 0)}% used"
    )
    print(f"  Screen-on weighted full runtime: {robust.get('weighted_full_runtime') or 'n/a'}")
    print(f"  Screen-on median session projection: {robust.get('median_projected_full_runtime') or 'n/a'}")
    if loose.get("weighted_full_runtime") != robust.get("weighted_full_runtime"):
        print(f"  Looser 5m/1% screen-on estimate: {loose.get('weighted_full_runtime') or 'n/a'}")
    print(f"  Wall-clock battery runtime including sleep: {wall.get('weighted_full_runtime') or 'n/a'}")

    power_source = long_term_runtime if long_term_robust.get("weighted_avg_power_w") is not None else runtime
    power_summary = power_source.get("screen_on_robust", {})
    if power_summary.get("weighted_avg_power_w") is not None:
        print()
        print("Power Usage Estimate")
        power_span = power_source.get("log_span", {})
        label = "Longer stored history" if power_source is long_term_runtime else "pmset history"
        print(f"  Source: {label}")
        print(f"  Span: {power_span.get('start', 'n/a')} -> {power_span.get('end', 'n/a')}")
        print(
            "  Screen-on sample: "
            f"{power_summary.get('session_count', 0)} sessions, "
            f"{power_summary.get('observed_duration', '0m')} observed, "
            f"{power_summary.get('observed_drop_pct', 0)}% used"
        )
        print_power_usage(power_summary)

    recent = runtime.get("recent_screen_sessions", [])
    if recent:
        print()
        print("Recent Screen-On Sessions")
        for session in recent[-5:]:
            print(
                "  "
                f"{session['start'][:16]} -> {session['end'][:16]} | "
                f"{session['duration']} | "
                f"{session['start_charge']}%->{session['end_charge']}% | "
                f"projected {session['projected_full_runtime']}"
            )

    if report.get("errors"):
        print()
        print("Errors")
        for error in report["errors"]:
            print(f"  {error}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report macOS battery drain, health, and recent runtime estimates."
    )
    parser.add_argument("--json", action="store_true", help="print structured JSON output")
    args = parser.parse_args()

    if sys.platform != "darwin":
        print("battery-stats only supports macOS battery telemetry.", file=sys.stderr)
        return 2

    report = collect_report()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_human(report)
    return 1 if report.get("errors") else 0


if __name__ == "__main__":
    raise SystemExit(main())
