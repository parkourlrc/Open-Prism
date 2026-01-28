from __future__ import annotations

import os
import subprocess
from typing import Iterable


def _list_descendant_pids_windows(root_pid: int) -> list[int]:
    script = f"""
$root = {root_pid}
$self = $PID
function Get-Desc([int]$p) {{
  $kids = Get-CimInstance Win32_Process -Filter "ParentProcessId=$p" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty ProcessId
  foreach($k in $kids) {{
    if ($k -and $k -ne $self) {{
      $k
      Get-Desc $k
    }}
  }}
}}
Get-Desc $root | Sort-Object -Unique
"""
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", script],
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
        )
    except Exception:
        return []

    pids: list[int] = []
    for line in (out or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            pids.append(int(line))
        except ValueError:
            continue
    return [pid for pid in pids if pid > 0 and pid != root_pid]


def _taskkill_tree(pid: int) -> None:
    try:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        pass


def cleanup_child_processes(*, extra_pids: Iterable[int] = ()) -> None:
    """
    Best-effort cleanup of all child/grandchild processes started by this app.
    Intended to be called when closing the Tk window.
    """
    root_pid = os.getpid()

    pids: list[int] = []
    if os.name == "nt":
        pids.extend(_list_descendant_pids_windows(root_pid))

    for pid in extra_pids:
        if pid and pid != root_pid:
            pids.append(int(pid))

    # Deduplicate and kill.
    for pid in sorted(set(pids), reverse=True):
        if pid == root_pid:
            continue
        _taskkill_tree(pid)

