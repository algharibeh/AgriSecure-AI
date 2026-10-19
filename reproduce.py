"""Reproduce every AgriSecure-AI result with one command.

Part of the AgriSecure-AI project.

Runs the Phase 1 and Phase 2 scripts in order on the real tractor data, rebuilds
the figures, runs the C self-test when a C compiler is on the PATH, and then
compares what the run produced with what this commit has on record: the result
JSON files, the embedded headers, the exported model, the events list and the
dataset checksums in docs/DATASET_DATASHEET.md. A dated log of the whole run is
written to results/reproduction_log_<timestamp>.txt (not tracked by git).

Run with (Windows, from the repository root):

    .venv/Scripts/python.exe -I reproduce.py

or double-click reproduce.bat, which uses the repository's .venv and keeps the
window open when the run ends. Each step is announced as "[k/8] name (started
hh:mm:ss)", its own output streams live, a line every 20 s shows a quiet step is
still running, and "done in N s" closes it.

Options:
    --pause           wait for Enter before exiting (reproduce.bat passes this)
    --skip-sil        skip the software-in-the-loop replay (about three minutes
                      of wall-clock time; its latencies are timing-dependent)
    --skip-figures    skip scripts/make_figures.py
    --no-compare      run the scripts but do not compare against the record
    --cc PATH         C compiler to use for the self-test (default: the first
                      of gcc, cc, clang found on the PATH; skipped if none)
    --steps a,b,...   run only these steps, by name (see STEPS below)

Nothing here contacts any device or network; the SIL replay uses a python-can
virtual bus inside this process. The raw tractor data are not downloaded here:
see AVAILABILITY.md for the source (Mendeley DOI 10.17632/bbjtjrsxvx.2, CC BY 4.0).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"
RAW_DIR = ROOT / "data" / "tumosan_raw"
RESULTS = ROOT / "results"
DATASET = ROOT / "dataset"
EMBEDDED = ROOT / "embedded"
DATASHEET = ROOT / "docs" / "DATASET_DATASHEET.md"

# (name, script, what it writes)
STEPS = [
    ("build", "build_can_stream.py", "dataset/normal/field_*.parquet"),
    ("inject", "inject_anomalies.py", "dataset/attacked/field_*.parquet, dataset/events.csv"),
    ("detect", "detect_baseline.py", "results/metrics.json, results/test_scored.parquet"),
    ("train", "train_tiny_model.py", "results/metrics_phase2.json, results/tiny_model.npz"),
    ("export", "export_embedded.py", "embedded/model_weights.h, embedded/test_vectors.h, results/footprint_phase2.json"),
    ("sil", "sil_replay.py", "results/sil_phase2.json"),
    ("figures", "make_figures.py", "results/figures/*.png"),
    ("ctest", None, "self-test of embedded/tiny_ids.c (needs a C compiler)"),
]

# Files on record that the run regenerates and that can be compared exactly.
RECORD_JSON = ["results/metrics.json", "results/metrics_phase2.json", "results/footprint_phase2.json"]
RECORD_TEXT = ["embedded/model_weights.h", "embedded/test_vectors.h", "dataset/events.csv"]
RECORD_BIN = ["results/tiny_model.npz"]
RECORD_TIMING = "results/sil_phase2.json"

REL_TOL = 1e-9


class Log:
    def __init__(self, path: Path):
        self.path = path
        self.fh = open(path, "w", encoding="utf-8")

    def __call__(self, msg: str = "") -> None:
        print(msg, flush=True)
        self.fh.write(msg + "\n")
        self.fh.flush()

    def close(self) -> None:
        self.fh.close()


# --------------------------------------------------------------------------- #
# environment
# --------------------------------------------------------------------------- #
def check_environment(log: Log) -> None:
    log(f"Python {sys.version.split()[0]} at {sys.executable}")
    if sys.version_info[:2] != (3, 9):
        log("  note: the results on record were produced with Python 3.9.13; another version "
            "may change floating-point details or parquet bytes.")
    missing = []
    for mod in ("numpy", "pandas", "pyarrow", "scipy", "sklearn", "matplotlib", "can"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        log(f"  missing packages: {', '.join(missing)}; install with: "
            f"{sys.executable} -m pip install -r requirements.txt")
        sys.exit(2)
    tabs = sorted(RAW_DIR.glob("FIELD_*.tab"))
    if len(tabs) < 10:
        rars = list(RAW_DIR.glob("*.rar")) if RAW_DIR.exists() else []
        if rars:
            log(f"  found {rars[0].name} but only {len(tabs)} FIELD_*.tab files; trying to extract it")
            try:
                import rarfile  # type: ignore
                with rarfile.RarFile(str(rars[0])) as rf:
                    rf.extractall(str(RAW_DIR))
                tabs = sorted(RAW_DIR.glob("FIELD_*.tab"))
            except Exception as exc:  # rarfile needs an unrar/7z backend
                log(f"  extraction failed ({exc}); extract {rars[0].name} into data/tumosan_raw/ by hand")
    if len(tabs) < 10:
        log("  the real tractor data are not present: expected ten FIELD_*.tab files in data/tumosan_raw/.")
        log("  Source: Mendeley Data, DOI 10.17632/bbjtjrsxvx.2 (CC BY 4.0), archive FIELD_FILES.rar; "
            "see AVAILABILITY.md. Nothing is downloaded by this script.")
        sys.exit(2)
    log(f"  data: {len(tabs)} FIELD_*.tab files in data/tumosan_raw/")


def git_head() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                             text=True, check=True)
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout.strip()
        return out.stdout.strip() + (" (with uncommitted changes)" if dirty else "")
    except Exception:
        return "unknown (git not available)"


# --------------------------------------------------------------------------- #
# the record: what this commit has on file, before the run overwrites it
# --------------------------------------------------------------------------- #
def snapshot_record(tmp: Path, log: Log) -> dict:
    """Copy the tracked result files from git HEAD (or, failing that, from the
    working tree before the run) into tmp. Returns {relpath: Path}."""
    rec = {}
    use_git = True
    try:
        subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, check=True)
    except Exception:
        use_git = False
    for rel in RECORD_JSON + RECORD_TEXT + RECORD_BIN + [RECORD_TIMING]:
        dst = tmp / rel.replace("/", "__")
        got = False
        if use_git:
            r = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=ROOT, capture_output=True)
            if r.returncode == 0:
                dst.write_bytes(r.stdout)
                got = True
        if not got and (ROOT / rel).exists():
            shutil.copy2(ROOT / rel, dst)
            got = True
        if got:
            rec[rel] = dst
    log(f"  record taken from {'git HEAD' if use_git else 'the working tree before the run'}: "
        f"{len(rec)} files")
    return rec


# --------------------------------------------------------------------------- #
# running the steps
# --------------------------------------------------------------------------- #
def run_script(script: str, log: Log) -> float:
    t0 = time.time()
    # -u: unbuffered, so the step's own prints appear as they happen
    cmd = [sys.executable, "-I", "-u", str(SCRIPTS / script)]
    log(f"$ {' '.join(cmd)}")
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", bufsize=1, env=env)
    assert proc.stdout is not None
    last = [time.time()]
    stop = threading.Event()

    def heartbeat() -> None:
        # a line every 20 s of silence, so a long step visibly keeps running
        while not stop.wait(5):
            if time.time() - last[0] >= 20:
                print(f"  ... {script} still running ({time.time() - t0:.0f} s elapsed)", flush=True)
                last[0] = time.time()

    hb = threading.Thread(target=heartbeat, daemon=True)
    hb.start()
    try:
        for line in proc.stdout:
            log("  | " + line.rstrip("\n"))
            last[0] = time.time()
    finally:
        stop.set()
    rc = proc.wait()
    dt = time.time() - t0
    if rc != 0:
        log(f"  FAILED (exit {rc}) after {dt:.0f} s")
        raise SystemExit(f"{script} failed with exit code {rc}; see the log")
    log(f"  done in {dt:.0f} s")
    return dt


def find_cc(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    for name in ("gcc", "cc", "clang"):
        p = shutil.which(name)
        if p:
            return p
    return None


def run_ctest(cc: str | None, log: Log) -> tuple[str, str]:
    """Returns (status, detail). status in {'passed', 'failed', 'skipped'}."""
    if not cc:
        return "skipped", ("no C compiler on the PATH; the committed results/embedded_build_phase2.txt "
                           "records the self-test and the Cortex-M sizes from the Colab build")
    exe = EMBEDDED / ("tiny_ids.exe" if os.name == "nt" else "tiny_ids")
    cmd = [cc, "-std=c99", "-O2", "-Wall", "-o", str(exe), str(EMBEDDED / "tiny_ids.c"), "-lm"]
    log(f"$ {' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=EMBEDDED, capture_output=True, text=True)
    if r.stdout.strip():
        log("  | " + r.stdout.strip().replace("\n", "\n  | "))
    if r.stderr.strip():
        log("  | " + r.stderr.strip().replace("\n", "\n  | "))
    if r.returncode != 0:
        return "failed", f"compile failed with exit {r.returncode}"
    log(f"$ {exe}")
    r = subprocess.run([str(exe)], cwd=EMBEDDED, capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    log("  | " + out.replace("\n", "\n  | "))
    m = re.search(r"flag mismatches = (\d+)", out)
    if r.returncode == 0 and m and m.group(1) == "0":
        return "passed", out.splitlines()[0]
    return "failed", out.splitlines()[0] if out else f"exit {r.returncode}"


# --------------------------------------------------------------------------- #
# comparison
# --------------------------------------------------------------------------- #
def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def json_diff(a, b, path: str = "", out: list | None = None) -> list:
    """List of (path, recorded, reproduced) where the two JSON trees differ."""
    if out is None:
        out = []
    if _num(a) and _num(b):
        if a != b and not (abs(a - b) <= REL_TOL * max(abs(a), abs(b), 1.0)):
            out.append((path, a, b))
    elif isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append((f"{path}/{k}", a.get(k, "<absent>"), b.get(k, "<absent>")))
            else:
                json_diff(a[k], b[k], f"{path}/{k}", out)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append((f"{path}/len", len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            json_diff(x, y, f"{path}[{i}]", out)
    elif a != b:
        out.append((path, a, b))
    return out


def _norm(b: bytes) -> bytes:
    return b.replace(b"\r\n", b"\n")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def datasheet_checksums() -> dict:
    """{relpath: sha} from the checksum table in docs/DATASET_DATASHEET.md."""
    table = {}
    if not DATASHEET.exists():
        return table
    for line in DATASHEET.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*`([^`]+\.parquet)`\s*\|\s*`([0-9a-f]{64})`\s*\|", line)
        if m:
            table[m.group(1)] = m.group(2)
    return table


def compare(record: dict, ran: set, log: Log) -> list:
    """Compare the regenerated files with the record. Returns summary rows."""
    rows = []
    # exact JSON
    for rel in RECORD_JSON:
        step = {"results/metrics.json": "detect", "results/metrics_phase2.json": "train",
                "results/footprint_phase2.json": "export"}[rel]
        if step not in ran:
            continue
        if rel not in record:
            rows.append((rel, "no record", ""))
            continue
        a = json.loads(record[rel].read_text(encoding="utf-8"))
        b = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        a.pop("runtime_s", None); b.pop("runtime_s", None)
        for key in ("rule_throughput_frames_per_s", "rule_us_per_frame"):   # machine-speed figures
            a.pop(key, None); b.pop(key, None)
        d = json_diff(a, b)
        if not d:
            rows.append((rel, "identical", "every value matches the record (timing fields excluded)"))
        else:
            rows.append((rel, f"{len(d)} difference(s)", "; ".join(f"{p}: {x} -> {y}" for p, x, y in d[:6])))
            for p, x, y in d[:40]:
                log(f"    {rel}{p}: recorded {x!r}, reproduced {y!r}")
    # exact text / binary
    for rel in RECORD_TEXT + RECORD_BIN:
        step = {"embedded/model_weights.h": "export", "embedded/test_vectors.h": "export",
                "dataset/events.csv": "inject", "results/tiny_model.npz": "train"}[rel]
        if step not in ran:
            continue
        if rel not in record:
            rows.append((rel, "no record", ""))
            continue
        if rel in RECORD_TEXT:
            # git stores these with LF and checks them out with CRLF on Windows
            # (core.autocrlf); compare the text, not the line terminators.
            same = _norm(record[rel].read_bytes()) == _norm((ROOT / rel).read_bytes())
        else:
            same = record[rel].read_bytes() == (ROOT / rel).read_bytes()
        if same:
            rows.append((rel, "identical", "byte-for-byte" if rel in RECORD_BIN else "text identical (line endings ignored)"))
        elif rel == "results/tiny_model.npz":
            try:
                import numpy as np
                ra, rb = np.load(record[rel]), np.load(ROOT / rel)
                keys = sorted(set(ra.files) | set(rb.files))
                worst = 0.0
                for k in keys:
                    if k not in ra.files or k not in rb.files:
                        worst = float("inf"); break
                    x, y = ra[k], rb[k]
                    if x.shape != y.shape:
                        worst = float("inf"); break
                    if x.dtype.kind in "fiu" and y.dtype.kind in "fiu":
                        worst = max(worst, float(np.max(np.abs(x.astype(float) - y.astype(float)))) if x.size else 0.0)
                    elif not np.array_equal(x, y):
                        worst = float("inf")
                if worst == 0.0:
                    rows.append((rel, "identical", "arrays equal (archive bytes differ only in metadata)"))
                else:
                    rows.append((rel, "differs", f"max abs difference across arrays {worst:.3g}"))
            except Exception as exc:
                rows.append((rel, "differs", f"bytes differ; could not compare arrays ({exc})"))
        else:
            rows.append((rel, "differs", "bytes differ"))
    # timing-dependent SIL
    if "sil" in ran and RECORD_TIMING in record:
        a = json.loads(record[RECORD_TIMING].read_text(encoding="utf-8"))
        b = json.loads((ROOT / RECORD_TIMING).read_text(encoding="utf-8"))
        notes = []
        for sa, sb in zip(a.get("segments", []), b.get("segments", [])):
            det_a = {k: (sa.get(k) is not None) for k in ("rule_latency_ms", "model_latency_ms", "hybrid_latency_ms")}
            det_b = {k: (sb.get(k) is not None) for k in ("rule_latency_ms", "model_latency_ms", "hybrid_latency_ms")}
            flags_same = det_a == det_b and sa.get("pre_attack_false_flags") == sb.get("pre_attack_false_flags") \
                and sa.get("frames_replayed") == sb.get("frames_replayed") and sa.get("attack_frames") == sb.get("attack_frames")
            notes.append(f"{sa.get('family')}: hybrid {sa.get('hybrid_latency_ms')} -> {sb.get('hybrid_latency_ms')} ms"
                         + ("" if flags_same else " [DETECTION OUTCOME DIFFERS]"))
        rows.append((RECORD_TIMING, "timing-dependent", "; ".join(notes)))
    # dataset checksums against the datasheet
    if ran & {"build", "inject"}:
        table = datasheet_checksums()
        if not table:
            rows.append(("dataset checksums", "no datasheet table", ""))
        else:
            ok = bad = missing = 0
            for rel, sha in sorted(table.items()):
                p = ROOT / rel
                if not p.exists():
                    missing += 1
                    continue
                if sha256(p) == sha:
                    ok += 1
                else:
                    bad += 1
                    log(f"    checksum differs: {rel}")
            rows.append(("dataset checksums", "identical" if bad == 0 and missing == 0 else "differs",
                         f"{ok} of {len(table)} parquet files match docs/DATASET_DATASHEET.md"
                         + (f", {bad} differ" if bad else "") + (f", {missing} missing" if missing else "")))
    return rows


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--skip-sil", action="store_true")
    ap.add_argument("--skip-figures", action="store_true")
    ap.add_argument("--no-compare", action="store_true")
    ap.add_argument("--cc", default=None, help="C compiler for the self-test")
    ap.add_argument("--steps", default=None, help="comma-separated subset of: " + ",".join(s[0] for s in STEPS))
    ap.add_argument("--compare-only", action="store_true",
                    help="run nothing; compare the files now in the working tree with the record")
    ap.add_argument("--pause", action="store_true",
                    help="wait for Enter before exiting (keeps a double-clicked console window open)")
    args = ap.parse_args()

    RESULTS.mkdir(exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M")
    log = Log(RESULTS / f"reproduction_log_{stamp}.txt")
    t_all = time.time()
    log(f"AgriSecure-AI reproduction run, {_dt.datetime.now():%Y-%m-%d %H:%M}, repository at {git_head()}")
    log(f"Platform: {sys.platform}; log: {log.path.relative_to(ROOT)}")
    log()
    log("Environment")
    check_environment(log)

    wanted = [s[0] for s in STEPS]
    if args.steps:
        wanted = [s.strip() for s in args.steps.split(",") if s.strip()]
        unknown = [s for s in wanted if s not in {x[0] for x in STEPS}]
        if unknown:
            log(f"unknown step(s): {', '.join(unknown)}")
            return 2
    if args.skip_sil and "sil" in wanted:
        wanted.remove("sil")
    if args.skip_figures and "figures" in wanted:
        wanted.remove("figures")
    if args.compare_only:
        args.no_compare = False
        wanted = []

    tmp = Path(tempfile.mkdtemp(prefix="agrisecure_record_"))
    record = {}
    if not args.no_compare:
        log()
        log("Record")
        record = snapshot_record(tmp, log)

    log()
    log("Steps: " + (", ".join(wanted) if wanted else "none (--compare-only)"))
    timings = []
    ran: set = set()
    if args.compare_only:
        ran = {s[0] for s in STEPS if s[0] != "ctest"}
    ctest = ("not run", "")
    for k, (name, script, writes) in enumerate([s for s in STEPS if s[0] in wanted], start=1):
        log()
        log(f"[{k}/{len(wanted)}] {name}  (started {_dt.datetime.now():%H:%M:%S}) -> {writes}")
        if name == "ctest":
            t0 = time.time()
            ctest = run_ctest(find_cc(args.cc), log)
            timings.append((name, time.time() - t0))
            log(f"  self-test: {ctest[0]}; {ctest[1]}")
        else:
            timings.append((name, run_script(script, log)))
        ran.add(name)

    rows = []
    if not args.no_compare and record:
        log()
        log("Comparison with the record")
        rows = compare(record, ran, log)

    log()
    log("=" * 78)
    log("SUMMARY")
    log("=" * 78)
    for name, dt in timings:
        log(f"  {name:<8} {dt:7.0f} s")
    log(f"  total    {time.time() - t_all:7.0f} s")
    if rows:
        log()
        w = max(len(r[0]) for r in rows)
        for rel, status, detail in rows:
            log(f"  {rel:<{w}}  {status:<18}  {detail}")
    if "ctest" in ran:
        log()
        log(f"  C self-test: {ctest[0]}; {ctest[1]}")
    log()
    verdict = "all compared files match the record" if rows and all(
        r[1] in ("identical", "timing-dependent") for r in rows) else (
        "differences found; see above" if rows else "no comparison made")
    log(f"Result: {verdict}.")
    if ran - {"ctest"} and not args.compare_only:
        log("Note: the run rewrote the tracked result files in place. `git diff --stat` shows what moved; "
            "machine-speed fields (throughput, run time, SIL latencies) and PNG bytes are expected to differ. "
            "`git checkout -- results` restores the record.")
    log(f"Log written to {log.path}")
    log.close()
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if verdict.startswith("all") or not rows else 1


def _entry() -> int:
    pause = "--pause" in sys.argv
    try:
        return main()
    except SystemExit as exc:
        if exc.code not in (0, None):
            print(f"\nStopped: {exc.code}", flush=True)
        return exc.code if isinstance(exc.code, int) else 1
    except KeyboardInterrupt:
        print("\nInterrupted.", flush=True)
        return 130
    except Exception:
        traceback.print_exc()
        return 1
    finally:
        if pause:
            try:
                input("\nPress Enter to close this window...")
            except EOFError:
                pass


if __name__ == "__main__":
    sys.exit(_entry())
