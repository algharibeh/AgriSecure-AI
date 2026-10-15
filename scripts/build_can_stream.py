"""Reconstruct an attack-free J1939 CAN frame stream from the Tumosan signals.

Part of the AgriSecure-AI project.

Input : data/tumosan_raw/FIELD_*.tab  (real decoded signals, 10 Hz, CC BY 4.0)
Output: dataset/normal/<field>.parquet (one row per reconstructed CAN frame)

For every 100 ms signal row, each J1939 parameter group is emitted at its
standard transmission period and its payload is packed with the real recorded
values. A round-trip decode check asserts the packing is lossless to SPN
resolution. No anomalies are added here.

Run with:  .venv/Scripts/python.exe -I scripts/build_can_stream.py
"""
from __future__ import annotations
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C


def build_field(tab_path: Path) -> pd.DataFrame:
    rows = []
    roundtrip_err = 0.0
    n_checked = 0
    # tiny deterministic intra-timestamp offset so global ordering is stable
    pgn_order = {s.pgn: i for i, s in enumerate(C.PGN_SPECS)}
    for row in C.load_tab(tab_path):
        t_ms = row.get("time_ms")
        if t_ms is None:
            continue
        t_ms = int(t_ms)
        for spec in C.PGN_SPECS:
            if t_ms % spec.rate_ms != 0:
                continue
            data = C.pack_frame(spec, row)
            # round-trip check on the primary numeric fields
            for fld in spec.fields:
                if fld.name in row and row[fld.name] is not None:
                    dec = C.decode_field(data, fld)
                    if dec is not None:
                        roundtrip_err = max(roundtrip_err,
                                             abs(dec - row[fld.name]) - fld.resolution)
                        n_checked += 1
            t_s = t_ms / 1000.0 + pgn_order[spec.pgn] * 1e-4
            rows.append((
                round(t_s, 4),
                f"{spec.can_id:08X}",
                spec.pgn,
                spec.label,
                spec.priority,
                spec.source_addr,
                8,
                data.hex().upper(),
                0,
                "none",
            ))
    df = pd.DataFrame(rows, columns=C.FRAME_COLUMNS)
    df.sort_values("t_s", kind="stable", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df, roundtrip_err, n_checked


def main():
    out_dir = C.DATASET_DIR / "normal"
    out_dir.mkdir(parents=True, exist_ok=True)
    tabs = sorted(C.RAW_DIR.glob("FIELD_*.tab"))
    if not tabs:
        sys.exit(f"no .tab files under {C.RAW_DIR}")
    total = 0
    worst = 0.0
    summary = []
    for tab in tabs:
        field = tab.name.split("_TUMOSAN")[0].lower()  # field_1, field_2, ...
        df, err, n = build_field(tab)
        worst = max(worst, err)
        total += len(df)
        df.to_parquet(out_dir / f"{field}.parquet", index=False)
        dur = df["t_s"].max() - df["t_s"].min() if len(df) else 0
        summary.append((field, len(df), round(dur, 1)))
        print(f"{field:10s} frames={len(df):7d} dur={dur:7.1f}s "
              f"roundtrip_margin={err:+.4g}")
    print(f"\nTOTAL frames={total}  worst_roundtrip_margin={worst:+.4g} "
          f"(<=0 means lossless to SPN resolution)")
    if worst > 1e-6:
        sys.exit("ERROR: payload packing is not lossless; check SPN definitions")
    print("OK: all payloads re-decode to the recorded values within resolution.")


if __name__ == "__main__":
    main()
