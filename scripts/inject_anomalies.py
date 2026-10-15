"""Inject reproducible, labelled anomaly scenarios into the reconstructed stream.

Part of the AgriSecure-AI project.

This operates ONLY on the simulated CAN frame stream produced by
build_can_stream.py. It performs no action against any real device or network.
Each anomaly family models a documented CAN/J1939 threat; injected or modified
frames are labelled attack=1 with their family in attack_type. All randomness is
seeded so the dataset is byte-reproducible.

Split: fields 1-6 stay clean (detector training, attack-free). Fields 7-10
receive attacks (evaluation). Output mirrors dataset/normal into
dataset/attacked/, plus dataset/events.csv listing every injected episode.

Families:
  flood      - DoS: burst of highest-priority frames from a foreign address
  injection  - fabricated EEC1 frames (real address) with implausible values
  masquerade - EEC1 frames from a foreign address (two sources, one PGN)
  replay     - an earlier real frame block re-sent later (stale values)
  freeze     - an existing sensor PGN held at a constant payload (stuck sensor)

Run: .venv/Scripts/python.exe -I scripts/inject_anomalies.py
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

SEED = 20261015
TRAIN_FIELDS = [f"field_{i}" for i in range(1, 7)]
TEST_FIELDS = [f"field_{i}" for i in range(7, 11)]

FOREIGN_SA_FLOOD = 0xF5
FOREIGN_SA_MASQ = 0xF9
EEC1 = C.PGN_BY_LABEL["EEC1"]
CCVS1 = C.PGN_BY_LABEL["CCVS1"]

# episodes per field, (duration_s) for each family
PLAN = {
    "flood":      dict(n=4, dur=1.0),
    "injection":  dict(n=4, dur=5.0),
    "masquerade": dict(n=4, dur=5.0),
    "replay":     dict(n=3, dur=4.0),
    "freeze":     dict(n=3, dur=6.0),
}


def _frame(t_s, spec, data, sa, attack, atype, can_id=None, pgn=None, prio=None):
    cid = spec.can_id if can_id is None else can_id
    if sa is not None and can_id is None:
        cid = (cid & ~0xFF) | sa
    return (
        round(float(t_s), 4),
        f"{cid:08X}",
        spec.pgn if pgn is None else pgn,
        spec.label if pgn is None else "ATTACK",
        spec.priority if prio is None else prio,
        sa if sa is not None else spec.source_addr,
        8,
        data.hex().upper() if isinstance(data, (bytes, bytearray)) else data,
        attack,
        atype,
    )


def pick_windows(rng, t0, t1, n, dur, guard=20.0):
    """Non-overlapping [start, start+dur] windows inside (t0+guard, t1-guard)."""
    lo, hi = t0 + guard, t1 - guard - dur
    out = []
    if hi <= lo:
        return out
    tries = 0
    while len(out) < n and tries < 2000:
        tries += 1
        s = rng.uniform(lo, hi)
        if all(abs(s - a) > dur + 5 for a, _ in out):
            out.append((s, s + dur))
    return sorted(out)


def inject_field(df: pd.DataFrame, rng, field) -> tuple:
    t0, t1 = df["t_s"].min(), df["t_s"].max()
    new_rows = []
    events = []

    # flood: ~1 ms spacing, priority 0, foreign SA, PGN 0 (bogus)
    for s, e in pick_windows(rng, t0, t1, PLAN["flood"]["n"], PLAN["flood"]["dur"]):
        t = s
        while t < e:
            data = bytes(int(x) for x in rng.integers(0, 256, 8))
            cid = (0 << 26) | FOREIGN_SA_FLOOD  # priority 0, PF/PS 0
            new_rows.append(_frame(t, EEC1, data, FOREIGN_SA_FLOOD, 1, "flood",
                                   can_id=cid, pgn=0, prio=0))
            t += rng.uniform(0.0008, 0.0014)
        events.append((field, "flood", round(s, 3), round(e, 3), 0))

    # injection: fabricated EEC1 at ~50 ms, real SA, implausible engine speed
    for s, e in pick_windows(rng, t0, t1, PLAN["injection"]["n"], PLAN["injection"]["dur"]):
        t = s
        bad_rpm = float(rng.choice([0.0, 2900.0, 2950.0]))
        while t < e:
            row = {"EngineSpeed": bad_rpm,
                   "ActualEngine_PercTorque": float(rng.uniform(100, 120))}
            data = C.pack_frame(EEC1, row)
            new_rows.append(_frame(t, EEC1, data, C.SA_ENGINE, 1, "injection"))
            t += rng.uniform(0.045, 0.055)
        events.append((field, "injection", round(s, 3), round(e, 3), 0))

    # masquerade: EEC1 from foreign SA at ~100 ms, plausible value
    for s, e in pick_windows(rng, t0, t1, PLAN["masquerade"]["n"], PLAN["masquerade"]["dur"]):
        t = s
        while t < e:
            row = {"EngineSpeed": float(rng.uniform(1800, 2300)),
                   "ActualEngine_PercTorque": float(rng.uniform(40, 90))}
            data = C.pack_frame(EEC1, row)
            new_rows.append(_frame(t, EEC1, data, FOREIGN_SA_MASQ, 1, "masquerade"))
            t += rng.uniform(0.095, 0.105)
        events.append((field, "masquerade", round(s, 3), round(e, 3), 0))

    # replay: copy an earlier EEC1 block and re-send it later verbatim
    eec1 = df[df["label"] == "EEC1"].reset_index(drop=True)
    for s, e in pick_windows(rng, t0, t1, PLAN["replay"]["n"], PLAN["replay"]["dur"]):
        dur = e - s
        src0 = rng.uniform(t0 + 10, s - dur - 10)
        block = eec1[(eec1["t_s"] >= src0) & (eec1["t_s"] < src0 + dur)]
        shift = s - src0
        for _, r in block.iterrows():
            data = bytes.fromhex(r["data_hex"])
            new_rows.append(_frame(r["t_s"] + shift, EEC1, data, C.SA_ENGINE,
                                   1, "replay"))
        events.append((field, "replay", round(s, 3), round(e, 3), 0))

    df = pd.concat([df, pd.DataFrame(new_rows, columns=C.FRAME_COLUMNS)],
                   ignore_index=True)

    # freeze: hold an existing EEC1 block at the payload just before the window
    # (stuck engine-speed sensor). EEC1 varies every frame under load, so a hold
    # is a genuine anomaly, unlike wheel speed which is often naturally constant.
    for s, e in pick_windows(rng, t0, t1, PLAN["freeze"]["n"], PLAN["freeze"]["dur"]):
        mask = (df["label"] == "EEC1") & (df["t_s"] >= s) & (df["t_s"] < e) & (df["attack"] == 0)
        before = df[(df["label"] == "EEC1") & (df["t_s"] < s) & (df["attack"] == 0)]
        if before.empty or mask.sum() == 0:
            continue
        held = before.iloc[-1]["data_hex"]
        df.loc[mask, "data_hex"] = held
        df.loc[mask, "attack"] = 1
        df.loc[mask, "attack_type"] = "freeze"
        if int(mask.sum()):
            events.append((field, "freeze", round(s, 3), round(e, 3), int(mask.sum())))

    df.sort_values("t_s", kind="stable", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df, events


def main():
    rng = np.random.default_rng(SEED)
    out_dir = C.DATASET_DIR / "attacked"
    out_dir.mkdir(parents=True, exist_ok=True)
    norm = C.DATASET_DIR / "normal"
    all_events = []
    for field in TEST_FIELDS:
        df = pd.read_parquet(norm / f"{field}.parquet")
        n_before = len(df)
        df, events = inject_field(df, rng, field)
        df.to_parquet(out_dir / f"{field}.parquet", index=False)
        all_events += events
        atk = int((df["attack"] == 1).sum())
        print(f"{field:10s} frames {n_before:7d} -> {len(df):7d}  "
              f"attack_frames={atk:6d} ({100*atk/len(df):.2f}%)  "
              f"episodes={len(events)}")
    ev = pd.DataFrame(all_events,
                      columns=["field", "attack_type", "t_start", "t_end", "n_frames"])
    ev.to_csv(C.DATASET_DIR / "events.csv", index=False)
    print(f"\nepisodes by family:\n{ev['attack_type'].value_counts().to_string()}")
    print(f"\ntrain (clean) fields: {TRAIN_FIELDS}")
    print(f"test  (attacked) fields: {TEST_FIELDS}")
    print(f"events -> {C.DATASET_DIR / 'events.csv'}")


if __name__ == "__main__":
    main()
