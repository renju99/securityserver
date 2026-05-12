# -*- coding: utf-8 -*-
"""ZKTeco iClock ATTLOG text parser (tab-separated)."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

LINE_SPLIT = re.compile(r"\r?\n")


def parse_zk_attlog_lines(body: str) -> list[dict[str, Any]]:
    if not body or not isinstance(body, str):
        return []
    out: list[dict[str, Any]] = []
    for raw in LINE_SPLIT.split(body):
        line = raw.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("\t")]
        if len(parts) < 2:
            continue
        user_id, timestamp_str = parts[0], parts[1]
        if not user_id or not timestamp_str:
            continue
        in_out = parts[2] if len(parts) > 2 and parts[2] != "" else "0"
        verify = parts[3] if len(parts) > 3 and parts[3] != "" else ""
        out.append(
            {
                "user_id": user_id,
                "timestamp_str": timestamp_str,
                "in_out_mode": in_out,
                "verify_type": verify,
                "line": line,
            }
        )
    return out


def zk_timestamp_to_datetime(ts: str) -> datetime | None:
    if not ts:
        return None
    normalized = ts if "T" in ts else ts.replace(" ", "T")
    try:
        # ZK sends local device time without TZ; treat as naive UTC-equivalent parse
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def zk_in_out_to_direction(in_out_mode: str) -> str:
    """Heuristic: even/0 = in, odd = out (common ZK convention; configurable per device)."""
    try:
        v = int(str(in_out_mode).strip() or "0")
        return "out" if v % 2 else "in"
    except ValueError:
        return "in"
