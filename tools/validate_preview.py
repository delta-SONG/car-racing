"""Run a frozen preview from an unrelated directory and validate its telemetry."""

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def save_hashes():
    root = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "SpeedHighway"
    return {name: digest(root / name) for name in ("save.json", "save3d.json")}


def working_set(pid):
    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    function = ctypes.windll.psapi.GetProcessMemoryInfo
    function.argtypes = (wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD)
    handle = kernel.OpenProcess(0x0400 | 0x0010, False, pid)
    if not handle:
        return None
    try:
        memory = Counters()
        memory.cb = ctypes.sizeof(memory)
        return memory.WorkingSetSize if function(handle, ctypes.byref(memory), memory.cb) else None
    finally:
        kernel.CloseHandle(handle)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("exe", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=600)
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--mode", choices=("classic", "escort"), default="escort")
    parser.add_argument("--allow-desktop", action="store_true",
                        help="Requires explicit user permission when using --native")
    args = parser.parse_args()
    if args.native and not args.allow_desktop:
        parser.error("Native validation requires explicit user permission and --allow-desktop")
    executable, output = args.exe.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise RuntimeError("Choose an empty output directory; old reports must not count as a new validation")
    before = save_hashes()
    command = [str(executable), "--mode", args.mode, "--smoke", str(args.seconds),
               "--report", str(output / "game-report.json"),
               "--screenshot", str(output / "gameplay.png")]
    if args.native:
        command.append("--native-smoke")
    started = time.monotonic()
    samples = []
    timeout = False
    with (output / "process.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=output, stdout=log, stderr=log,
                                   creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        next_sample = 0
        while process.poll() is None:
            elapsed = time.monotonic() - started
            if elapsed > args.seconds + 60:
                timeout = True
                # Terminate only the preview process tree launched by this check.
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=log, stderr=log, check=False)
                break
            if elapsed >= next_sample:
                samples.append(dict(seconds=round(elapsed, 2),
                                    bootloader_working_set=working_set(process.pid)))
                next_sample += 10
            time.sleep(0.2)
        code = process.wait(timeout=10)
    after = save_hashes()
    report_path = output / "game-report.json"
    game = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    checks = dict(exit_zero=code == 0, did_not_timeout=not timeout,
                  report_present=bool(game), legacy_and_3d_saves_unchanged=before == after,
                  screenshot_present=(output / "gameplay.png").is_file(),
                  sufficient_active_driving=game.get("active_driving_seconds", 0) >= args.seconds * 0.9,
                  sufficient_frames=game.get("playing_frames", 0) >= args.seconds * 20)
    if args.native:
        checks["average_fps_at_least_50"] = game.get("average_fps", 0) >= 50
    if args.mode == "escort" and args.seconds >= 90:
        checks["completed_at_least_one_escort"] = game.get("successful_escorts", 0) >= 1
    result = dict(exe_sha256=digest(executable), exe_bytes=executable.stat().st_size,
                  elapsed_seconds=time.monotonic() - started, exit_code=code, checks=checks,
                  game=game, bootloader_memory_samples=samples,
                  memory_note="Only the launching bootloader PID was sampled; not total game memory.",
                  passed=all(checks.values()), human_playtest=False)
    (output / "validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(dict(passed=result["passed"], checks=checks, output=str(output)), ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
