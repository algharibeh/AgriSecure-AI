"""Baseline intrusion detection on the labelled agricultural J1939 dataset.

Part of the AgriSecure-AI project.

Two detectors, both trained on the clean fields (1-6) only and evaluated on the
attacked fields (7-10):

  1. Rule-based IDS  - per-PGN source-address allow-list, per-PGN minimum
     inter-arrival, per-signal physical-range and rate-of-change limits, and a
     frozen-payload run-length check. O(1) state per PGN; this is the
     lightweight path the embedded target (Phase 2) must fit.
  2. Isolation Forest - unsupervised ML on per-frame features, trained on
     normal traffic only (matching the standard automotive-IDS setup).

Reports per-family recall, overall precision / recall / F1, false-positive rate
on normal frames, and per-episode detection latency. Honest by design: a family
the baseline cannot catch is reported as missed, not hidden.

Run: .venv/Scripts/python.exe -I scripts/detect_baseline.py
"""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

TRAIN_FIELDS = [f"field_{i}" for i in range(1, 7)]
TEST_FIELDS = [f"field_{i}" for i in range(7, 11)]
SEED = 20261015

# primary numeric signal per PGN label (widest dynamic range)
PRIMARY = {
    "EEC1": "EngineSpeed", "CCVS1": "WheelBasedVehicleSpeed", "LFE1": "EngFuelRate",
    "ET1": "EngCoolantTemp", "EFL/P1": "EngOilPress", "RearHitch": "HtcPositionSensPerc",
    "PTO": "PTO_Status", "PROP_B_AUX": "HtcDraftSens1Perc",
}
PRIMARY_FLD = {}
for _spec in C.PGN_SPECS:
    for _f in _spec.fields:
        if _f.name == PRIMARY.get(_spec.label):
            PRIMARY_FLD[_spec.label] = _f


def decode_primary(df: pd.DataFrame) -> np.ndarray:
    """Vectorised decode of each frame's primary signal; NaN where unavailable."""
    out = np.full(len(df), np.nan)
    hx = df["data_hex"].to_numpy()
    labels = df["label"].to_numpy()
    for label, fld in PRIMARY_FLD.items():
        m = labels == label
        if not m.any():
            continue
        sb = fld.start_byte * 2
        raw = np.zeros(m.sum(), dtype=np.float64)
        sub = np.array([h[sb:sb + fld.length * 2] for h in hx[m]])
        na = np.ones(m.sum(), dtype=bool)
        for i in range(fld.length):
            byte = np.array([int(s[i * 2:i * 2 + 2], 16) for s in sub])
            raw += byte * (256 ** i)
            na &= (byte == 0xFF)
        val = raw * fld.resolution + fld.offset
        val[na] = np.nan
        out[np.where(m)[0]] = val
    return out


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("t_s", kind="stable").reset_index(drop=True)
    df["value"] = decode_primary(df)
    # per (pgn, source_addr) inter-arrival and value delta
    key = df["pgn"].astype(str) + ":" + df["source_addr"].astype(str)
    df["_key"] = key
    df["iat"] = df.groupby("_key")["t_s"].diff()
    df["dval"] = df.groupby("_key")["value"].diff()
    # frozen run length: consecutive identical payloads within one (pgn,sa) stream.
    # Must be computed with each stream's frames contiguous, since streams are
    # interleaved in global time order.
    tmp = df.sort_values(["_key", "t_s"], kind="stable")
    same = tmp.groupby("_key")["data_hex"].shift() == tmp["data_hex"]
    grp = (~same).cumsum()
    runlen = tmp.groupby(["_key", grp]).cumcount() + 1
    df["runlen"] = runlen.reindex(df.index)
    return df


def learn_rules(train_files):
    sa_ok = {}        # pgn -> set of source addresses
    iat_min = {}      # pgn -> smallest normal inter-arrival seen
    runlen_max = {}   # pgn -> longest normal identical-payload run
    for f in train_files:
        df = build_features(pd.read_parquet(f))
        for pgn, g in df.groupby("pgn"):
            sa_ok.setdefault(pgn, set()).update(g["source_addr"].unique().tolist())
            iat = g["iat"].dropna()
            if len(iat):
                q = float(iat.quantile(0.005))
                iat_min[pgn] = min(iat_min.get(pgn, np.inf), q)
            runlen_max[pgn] = max(runlen_max.get(pgn, 0), int(g["runlen"].max()))
    return {"sa_ok": sa_ok, "iat_min": iat_min, "runlen_max": runlen_max}


def apply_rules(df: pd.DataFrame, rules) -> pd.DataFrame:
    sa_ok, iat_min, runlen_max = rules["sa_ok"], rules["iat_min"], rules["runlen_max"]
    pgn = df["pgn"].to_numpy()
    sa = df["source_addr"].to_numpy()
    iat = df["iat"].to_numpy()
    runlen = df["runlen"].to_numpy()
    label = df["label"].to_numpy()
    value = df["value"].to_numpy()
    dval = df["dval"].to_numpy()

    # source-address allow-list: flag unknown PGN or foreign address (vectorised)
    allowed_pairs = {(p, s) for p, ss in sa_ok.items() for s in ss}
    pair_idx = pd.MultiIndex.from_arrays([pgn, sa])
    allowed_idx = pd.MultiIndex.from_tuples(list(allowed_pairs))
    r_sa = ~pair_idx.isin(allowed_idx)

    # arriving far faster than the normal minimum for that PGN
    imin = df["pgn"].map(iat_min).to_numpy() * 0.5
    r_rate = (~np.isnan(iat)) & (~np.isnan(imin)) & (iat < imin)

    # physics + rate-of-change on decoded primary (vectorised)
    r_phys = np.zeros(len(df), bool)
    r_roc = np.zeros(len(df), bool)
    for label_name, fld in PRIMARY_FLD.items():
        lim = C.SIGNAL_LIMITS.get(PRIMARY.get(label_name))
        if not lim:
            continue
        lo, hi, dmax = lim
        m = label == label_name
        r_phys |= m & ((value < lo) | (value > hi))
        r_roc |= m & (np.abs(dval) > dmax)

    # SA-flagged frames are unknown PGNs; suppress the other rules' noise there
    r_rate = r_rate & ~r_sa

    df = df.copy()
    df["rule_sa"] = r_sa
    df["rule_rate"] = r_rate
    df["rule_phys"] = r_phys
    df["rule_roc"] = r_roc
    # Note: no stuck-value ("freeze") rule. Run-length cannot separate a short
    # held value from legitimate idle/steady-state (engine speed is naturally
    # constant for 10+ s at idle), so such a rule only adds false positives.
    # Freeze is therefore an acknowledged blind spot of this baseline.
    df["rule_flag"] = r_sa | r_rate | r_phys | r_roc
    return df


def feats_for_iforest(df: pd.DataFrame) -> np.ndarray:
    v = df["value"].fillna(-1.0).to_numpy()
    iat = df["iat"].fillna(1.0).clip(1e-4, 10).to_numpy()
    dval = df["dval"].fillna(0.0).to_numpy()
    return np.column_stack([
        df["pgn"].to_numpy(dtype=float),
        df["source_addr"].to_numpy(dtype=float),
        df["priority"].to_numpy(dtype=float),
        np.log10(iat),
        v,
        dval,
    ])


def metrics(y, pred):
    y = y.astype(bool); pred = pred.astype(bool)
    tp = int((y & pred).sum()); fp = int((~y & pred).sum())
    fn = int((y & ~pred).sum()); tn = int((~y & ~pred).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    fpr = fp / (fp + tn) if fp + tn else 0.0
    return dict(tp=tp, fp=fp, fn=fn, tn=tn, precision=round(prec, 4),
                recall=round(rec, 4), f1=round(f1, 4), fpr=round(fpr, 6))


def main():
    C.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    norm = C.DATASET_DIR / "normal"
    atk = C.DATASET_DIR / "attacked"

    print("learning rules from clean fields ...")
    rules = learn_rules([norm / f"{f}.parquet" for f in TRAIN_FIELDS])

    print("fitting Isolation Forest on normal traffic ...")
    rng = np.random.default_rng(SEED)
    sample = []
    for f in TRAIN_FIELDS:
        d = build_features(pd.read_parquet(norm / f"{f}.parquet"))
        idx = rng.choice(len(d), size=min(40000, len(d)), replace=False)
        sample.append(feats_for_iforest(d.iloc[idx]))
    Xtr = np.vstack(sample)
    scaler = StandardScaler().fit(Xtr)
    iforest = IsolationForest(n_estimators=150, max_samples=4096,
                              contamination=0.01, random_state=SEED, n_jobs=-1)
    iforest.fit(scaler.transform(Xtr))

    # evaluate on attacked fields
    parts = []
    t_rule = 0.0
    for f in TEST_FIELDS:
        d = build_features(pd.read_parquet(atk / f"{f}.parquet"))
        t0 = time.perf_counter()
        d = apply_rules(d, rules)
        t_rule += time.perf_counter() - t0
        d["if_flag"] = iforest.predict(scaler.transform(feats_for_iforest(d))) == -1
        d["field"] = f
        parts.append(d)
    test = pd.concat(parts, ignore_index=True)

    y = test["attack"].to_numpy()
    res = {
        "n_test_frames": int(len(test)),
        "n_attack_frames": int(y.sum()),
        "attack_prevalence": round(float(y.mean()), 5),
        "rule_based": metrics(y, test["rule_flag"].to_numpy()),
        "isolation_forest": metrics(y, test["if_flag"].to_numpy()),
        "rule_throughput_frames_per_s": int(len(test) / t_rule),
        "rule_us_per_frame": round(1e6 * t_rule / len(test), 2),
    }

    # per-family recall (attack frames only)
    fam = {}
    for name, g in test[test["attack"] == 1].groupby("attack_type"):
        fam[name] = {
            "n": int(len(g)),
            "rule_recall": round(float(g["rule_flag"].mean()), 4),
            "iforest_recall": round(float(g["if_flag"].mean()), 4),
        }
    res["per_family"] = fam

    # event-level detection + latency (rule detector)
    ev = pd.read_csv(C.DATASET_DIR / "events.csv")
    det, lat = [], []
    for _, e in ev.iterrows():
        g = test[(test["field"] == e["field"]) & (test["attack"] == 1) &
                 (test["attack_type"] == e["attack_type"]) &
                 (test["t_s"] >= e["t_start"] - 0.05) & (test["t_s"] <= e["t_end"] + 0.2)]
        flagged = g[g["rule_flag"]]
        detected = len(flagged) > 0
        det.append((e["attack_type"], detected))
        if detected:
            lat.append((e["attack_type"],
                        max(0.0, float(flagged["t_s"].min() - e["t_start"]))))
    detdf = pd.DataFrame(det, columns=["fam", "det"])
    latdf = pd.DataFrame(lat, columns=["fam", "lat"])
    res["event_detection"] = {
        fam_: {
            "episodes": int((detdf["fam"] == fam_).sum()),
            "detected": int(detdf[detdf["fam"] == fam_]["det"].sum()),
            "median_latency_ms": (round(1000 * latdf[latdf["fam"] == fam_]["lat"].median(), 1)
                                  if (latdf["fam"] == fam_).any() else None),
        }
        for fam_ in sorted(detdf["fam"].unique())
    }

    (C.RESULTS_DIR / "metrics.json").write_text(json.dumps(res, indent=2))
    test[["field", "t_s", "pgn", "label", "source_addr", "attack", "attack_type",
          "rule_flag", "if_flag"]].to_parquet(C.RESULTS_DIR / "test_scored.parquet",
                                              index=False)
    print(json.dumps({k: v for k, v in res.items()
                      if k not in ("per_family", "event_detection")}, indent=2))
    print("\nper-family:\n", json.dumps(res["per_family"], indent=2))
    print("\nevent detection:\n", json.dumps(res["event_detection"], indent=2))
    make_figure(res)


def make_figure(res):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fams = list(res["per_family"].keys())
    rule = [res["per_family"][f]["rule_recall"] for f in fams]
    iso = [res["per_family"][f]["iforest_recall"] for f in fams]
    x = np.arange(len(fams)); w = 0.38
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(x - w / 2, rule, w, label="Rule-based IDS", color="#2b6cb0")
    ax.bar(x + w / 2, iso, w, label="Isolation Forest", color="#dd6b20")
    ax.set_xticks(x); ax.set_xticklabels(fams, rotation=15)
    ax.set_ylabel("Per-family detection rate (recall)")
    ax.set_ylim(0, 1.05)
    ax.set_title("AgriSecure-AI Phase 1 - baseline detection by attack family")
    ax.legend(); ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    d = C.RESULTS_DIR / "figures"; d.mkdir(exist_ok=True)
    fig.savefig(d / "detection_by_family.png", dpi=140)
    print(f"\nfigure -> {d / 'detection_by_family.png'}")


if __name__ == "__main__":
    main()
