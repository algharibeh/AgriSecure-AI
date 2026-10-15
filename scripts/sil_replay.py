"""Software-in-the-loop replay of attacked traffic over a virtual CAN bus.

Part of the AgriSecure-AI project.

This is SIL, not HIL. A sender replays a bounded segment of one attacked field
onto a python-can *virtual* bus at wall-clock rate; a receiver reads frames as
they arrive and runs the streaming hybrid detector (Phase 1 rules + the Phase 2
int8 spread-consistency model, in the same form as embedded/tiny_ids.c) frame
by frame.
Detection latency is measured on the wall clock: first flag time minus the
send time of the episode's first attack frame. Nothing leaves this process; no
physical interface, device, or network is involved.

Segments: for each attack family, the first episode of field_7, from 20 s
before it starts to 10 s after it ends. Run time is the sum of the segments
(about three minutes).

Run: .venv/Scripts/python.exe -I scripts/sil_replay.py
"""
from __future__ import annotations
import json
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pandas as pd
import can

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C
import detect_baseline as B
import train_tiny_model as T
from export_embedded import load_model, score_f32

FIELD = "field_7"
PRE_S, POST_S = 20.0, 10.0
GRID_S, WIN = 0.1, 10
CHANNEL = "agrisecure_sil"


class StreamingIDS:
    """Frame-by-frame hybrid detector mirroring embedded/tiny_ids.c."""

    def __init__(self, rules, model_npz):
        self.model = load_model(model_npz)          # the exported (int8) model
        self.thr = float(self.model["thr"])
        self.sa_ok = {p: next(iter(s)) for p, s in rules["sa_ok"].items()}
        self.iat_min = {p: 0.5 * v for p, v in rules["iat_min"].items()}
        self.spec = {s.pgn: s for s in C.PGN_SPECS}
        self.primary = {s.pgn: B.PRIMARY_FLD.get(s.label) for s in C.PGN_SPECS}
        self.limits = {s.pgn: C.SIGNAL_LIMITS.get(B.PRIMARY.get(s.label)) for s in C.PGN_SPECS}
        self.eec1 = C.PGN_BY_LABEL["EEC1"]
        self.torque_fld = next(f for f in self.eec1.fields if f.name == "ActualEngine_PercTorque")
        self.reset()

    def reset(self):
        self.last = {}              # pgn -> (t, val)
        self.cell = None
        self.cur = [np.nan] * 4     # rpm, torque, fuel, speed of the current cell
        self.ring = np.zeros((WIN, 4), np.float32)
        self.count = 0
        self.head = 0

    @staticmethod
    def pgn_of(arb_id: int) -> int:
        pf = (arb_id >> 16) & 0xFF
        pgn = (arb_id >> 8) & 0x3FFFF
        return pgn if pf >= 240 else (pgn & 0x3FF00)

    def _features(self):
        r = self.ring
        mean = r.mean(axis=0); std = np.log10(r.std(axis=0) + T.STD_EPS)
        first = r[self.head]; last = r[(self.head + WIN - 1) % WIN]
        return np.stack([mean, std, last - first], axis=1).ravel()

    def _score(self, feat):
        return float(score_f32(self.model, feat.astype(np.float32)[None, :])[0])

    def process(self, arb_id: int, data: bytes, t_s: float):
        """Returns (rule_mask, model_flag_or_None, score_or_None)."""
        pgn, sa = self.pgn_of(arb_id), arb_id & 0xFF
        r = 0
        spec = self.spec.get(pgn)
        if spec is None or sa != self.sa_ok.get(pgn, -1):
            r |= 1
        val = None
        if spec is not None:
            fld = self.primary.get(pgn)
            val = C.decode_field(bytearray(data), fld) if fld else None
            if not (r & 1):
                lt = self.last.get(pgn)
                if lt is not None:
                    if t_s - lt[0] < self.iat_min.get(pgn, 0.0):
                        r |= 2
                    lim = self.limits.get(pgn)
                    if lim and val is not None and lt[1] is not None and abs(val - lt[1]) > lim[2]:
                        r |= 8
                lim = self.limits.get(pgn)
                if lim and val is not None and (val < lim[0] or val > lim[1]):
                    r |= 4
                self.last[pgn] = (t_s, val)
        # window path: legitimate-address signals only
        mflag, score = None, None
        if not (r & 1) and spec is not None and spec.label in ("EEC1", "LFE1", "CCVS1"):
            c = int(t_s // GRID_S)
            if self.cell is not None and c != self.cell:
                mflag, score = self._push_cell()
            self.cell = c
            if spec.label == "EEC1":
                self.cur[0] = val if val is not None else self.cur[0]
                tq = C.decode_field(bytearray(data), self.torque_fld)
                self.cur[1] = tq if tq is not None else self.cur[1]
            elif spec.label == "LFE1":
                self.cur[2] = val if val is not None else self.cur[2]
            else:
                self.cur[3] = val if val is not None else self.cur[3]
        return r, mflag, score

    def _push_cell(self):
        if any(np.isnan(v) for v in self.cur):
            # hold last known values (ECU behaviour) until every signal has been seen
            if self.count == 0:
                return None, None
            prev = self.ring[(self.head + WIN - 1) % WIN]
            self.cur = [p if np.isnan(v) else v for v, p in zip(self.cur, prev)]
        self.ring[self.head] = self.cur
        self.head = (self.head + 1) % WIN
        self.count = min(self.count + 1, WIN)
        if self.count < WIN:
            return None, None
        s = self._score(self._features())
        return s > self.thr, s


def sender(bus, frames: pd.DataFrame, t0_seg: float, wall0: float, sent_log: list, done: threading.Event):
    for row in frames.itertuples(index=False):
        target = wall0 + (row.t_s - t0_seg)
        now = time.perf_counter()
        if target > now:
            time.sleep(target - now)
        msg = can.Message(arbitration_id=int(row.can_id_hex, 16), is_extended_id=True,
                          data=bytes.fromhex(row.data_hex), timestamp=time.perf_counter())
        bus.send(msg)
        if row.attack:
            sent_log.append((time.perf_counter(), row.attack_type))
    done.set()


def run_segment(ids: StreamingIDS, frames: pd.DataFrame, episode) -> dict:
    tx = can.Bus(interface="virtual", channel=CHANNEL, receive_own_messages=False)
    rx = can.Bus(interface="virtual", channel=CHANNEL, receive_own_messages=False)
    ids.reset()
    t0_seg = float(frames["t_s"].iloc[0])
    sent, done = [], threading.Event()
    wall0 = time.perf_counter() + 0.2
    th = threading.Thread(target=sender, args=(tx, frames, t0_seg, wall0, sent, done), daemon=True)
    th.start()
    n = 0; proc_t = 0.0
    first_rule = first_model = None
    clean_rule_fp = clean_model_fp = 0
    atk_start_wall = None
    seg_wall_start = wall0
    while True:
        msg = rx.recv(timeout=0.2)
        if msg is None:
            if done.is_set():
                break
            continue
        t_wall = time.perf_counter()
        t_rel = t_wall - seg_wall_start + t0_seg          # receiver's own clock, seconds
        p0 = time.perf_counter()
        r, mflag, score = ids.process(msg.arbitration_id, bytes(msg.data), t_rel)
        proc_t += time.perf_counter() - p0
        n += 1
        if sent and atk_start_wall is None:
            atk_start_wall = sent[0][0]
        in_attack = atk_start_wall is not None and t_wall >= atk_start_wall
        if r and in_attack and first_rule is None:
            first_rule = t_wall
        if mflag and in_attack and first_model is None:
            first_model = t_wall
        if not in_attack:
            clean_rule_fp += bool(r)
            clean_model_fp += bool(mflag)
    th.join()
    tx.shutdown(); rx.shutdown()
    return {
        "family": episode["attack_type"], "field": FIELD,
        "segment_s": [round(t0_seg, 3), round(float(frames["t_s"].iloc[-1]), 3)],
        "frames_replayed": int(n), "attack_frames": int(frames["attack"].sum()),
        "rule_latency_ms": round(1000 * (first_rule - atk_start_wall), 1) if first_rule else None,
        "model_latency_ms": round(1000 * (first_model - atk_start_wall), 1) if first_model else None,
        "hybrid_latency_ms": (round(1000 * (min(x for x in (first_rule, first_model) if x) - atk_start_wall), 1)
                              if (first_rule or first_model) else None),
        "pre_attack_false_flags": {"rule_frames": int(clean_rule_fp), "model_windows": int(clean_model_fp)},
        "us_per_frame_processing": round(1e6 * proc_t / max(n, 1), 1),
    }


def main():
    rules = B.learn_rules([C.DATASET_DIR / "normal" / f"{f}.parquet" for f in B.TRAIN_FIELDS])
    ids = StreamingIDS(rules, C.RESULTS_DIR / "tiny_model.npz")
    df = pd.read_parquet(C.DATASET_DIR / "attacked" / f"{FIELD}.parquet").sort_values("t_s", kind="stable")
    ev = pd.read_csv(C.DATASET_DIR / "events.csv")
    ev = ev[ev["field"] == FIELD].groupby("attack_type", sort=False).first().reset_index()
    out = []
    for _, e in ev.iterrows():
        seg = df[(df["t_s"] >= e["t_start"] - PRE_S) & (df["t_s"] <= e["t_end"] + POST_S)]
        print(f"{e['attack_type']:10s} replaying {len(seg)} frames over "
              f"{seg['t_s'].iloc[-1] - seg['t_s'].iloc[0]:.0f} s ...", flush=True)
        r = run_segment(ids, seg, e)
        print("   ", json.dumps(r), flush=True)
        out.append(r)
    res = {"mode": "software-in-the-loop (python-can virtual bus, wall-clock replay); not HIL",
           "detector": "Phase 1 rules + int8 spread-consistency model, streaming (mirror of embedded/tiny_ids.c)",
           "segments": out}
    (C.RESULTS_DIR / "sil_phase2.json").write_text(json.dumps(res, indent=2))
    print(f"\n-> {C.RESULTS_DIR / 'sil_phase2.json'}")


if __name__ == "__main__":
    main()
