"""Phase 2, first result: a tiny context model for the anomalies the rules miss.

Part of the AgriSecure-AI project.

The Phase 1 rule-based IDS catches structural attacks (foreign address, impossible
rate, out-of-physics value) but is blind to a frozen sensor value and to
injected or replayed frames whose values stay inside the physical envelope.
This script trains small context models on one-second windows of the decoded
engine and vehicle signals, using clean traffic only, and evaluates them on the
attacked fields alone and combined with the rules (hybrid).

Models (both trained on clean fields 1-5; threshold set on clean field 6 at the
99.9 % quantile of the clean score, i.e. a 0.1 % window false-positive target):
  SPR  - spread-consistency model, 5 -> 8 -> 8 -> 1, ReLU. Predicts the log
         spread of fuel rate in the window from the log spread of engine speed,
         torque and wheel speed and the mean engine speed and torque. Anomaly
         score = squared residual. On a governed diesel the fuel rate only
         varies when load varies, so a frozen engine-speed/torque payload under
         a moving fuel rate is a physical inconsistency. This is the model
         exported to the embedded reference (export_embedded.py).
  AE   - window autoencoder, 12 -> 6 -> 3 -> 6 -> 12, ReLU, anomaly score =
         mean squared reconstruction error. Reported as the traffic-pattern
         variant; it catches injection but dilutes a single frozen signal
         across twelve features.

Windows: 1.0 s long, 0.1 s hop, over the 100 ms grid of EEC1 (engine speed,
torque), LFE1 (fuel rate) and CCVS1 (wheel speed) from the legitimate engine
address only (frames the Phase 1 source-address rule rejects are dropped first,
as the hybrid pipeline would). Per signal: mean, log10 of the standard
deviation (plus 0.01, so a frozen signal reads -2) and end-to-start change over
the window. In clean traffic, engine speed and torque are exactly constant only
with the engine off, when fuel rate is flat too; the log spread makes that
pattern learnable.

Everything here runs on the simulated frame stream of Phase 1; no vehicle, no
bus, no action against any real system. Measured numbers only; a family the
model does not catch is reported as missed.

Run: .venv/Scripts/python.exe -I scripts/train_tiny_model.py
"""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neural_network import MLPRegressor

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C
import detect_baseline as B

SEED = 20261015
TRAIN_FIELDS = [f"field_{i}" for i in range(1, 6)]
THRESH_FIELD = "field_6"
TEST_FIELDS = [f"field_{i}" for i in range(7, 11)]

GRID_S = 0.1          # signal grid (EEC1/LFE1/CCVS1 broadcast period)
WIN = 10              # window length in grid steps (1.0 s)
HOP = 1               # hop in grid steps (0.1 s)
FPR_TARGET = 0.001    # threshold = (1 - FPR_TARGET) quantile of clean held-out scores
STD_EPS = 0.01        # spread feature = log10(std + STD_EPS); frozen -> -2

SIGNALS = ["rpm", "torque", "fuel", "speed"]
FEATURES = [f"{s}_{st}" for s in SIGNALS for st in ("mean", "std", "chg")]
SPR_IN = ["rpm_std", "torque_std", "rpm_mean", "torque_mean", "speed_std"]
SPR_OUT = "fuel_std"
MODELS = ("rule", "ae", "spr", "hyb_ae", "hyb_spr")

EEC1 = C.PGN_BY_LABEL["EEC1"]
TORQUE_FLD = next(f for f in EEC1.fields if f.name == "ActualEngine_PercTorque")
RPM_FLD = next(f for f in EEC1.fields if f.name == "EngineSpeed")


def _decode(hx: np.ndarray, fld: C.SPNField) -> np.ndarray:
    sb = fld.start_byte * 2
    raw = np.zeros(len(hx))
    na = np.ones(len(hx), bool)
    for i in range(fld.length):
        b = np.array([int(h[sb + 2 * i: sb + 2 * i + 2], 16) for h in hx]) if len(hx) else np.zeros(0)
        raw += b * (256 ** i)
        na &= b == 0xFF
    v = raw * fld.resolution + fld.offset
    v[na] = np.nan
    return v


def signal_grid(df: pd.DataFrame, rules) -> pd.DataFrame:
    """Resample the four signals onto the 100 ms grid (last value per cell).

    Frames flagged by the source-address rule are dropped first; the remaining
    frames carry the engine address, so injected and replayed frames (which use
    the legitimate address) stay in, as they would on a real bus.
    Returns one row per grid cell with rpm, torque, fuel, speed, and the
    attack label of the cell (any attack frame of any PGN in that cell).
    """
    d = B.build_features(df)
    d = B.apply_rules(d, rules)
    cell = np.floor(d["t_s"].to_numpy() / GRID_S).astype(np.int64)
    d["cell"] = cell
    n0, n1 = int(cell.min()), int(cell.max())
    g = pd.DataFrame(index=np.arange(n0, n1 + 1))
    g.index.name = "cell"

    keep = ~d["rule_sa"].to_numpy()
    for label, cols in (("EEC1", ("rpm", "torque")), ("LFE1", ("fuel",)), ("CCVS1", ("speed",))):
        m = keep & (d["label"].to_numpy() == label)
        sub = d[m]
        hx = sub["data_hex"].to_numpy()
        if label == "EEC1":
            vals = {"rpm": _decode(hx, RPM_FLD), "torque": _decode(hx, TORQUE_FLD)}
        elif label == "LFE1":
            vals = {"fuel": sub["value"].to_numpy()}
        else:
            vals = {"speed": sub["value"].to_numpy()}
        last = pd.DataFrame(vals, index=sub["cell"].to_numpy()).groupby(level=0).last()
        for c in cols:
            g[c] = last[c].reindex(g.index)
    # forward-fill short gaps (an ECU holds the last value); label per cell
    g[SIGNALS] = g[SIGNALS].ffill().bfill()
    atk = d.groupby("cell")["attack"].max().reindex(g.index).fillna(0).astype(int)
    typ = d[d["attack"] == 1].groupby("cell")["attack_type"].agg(
        lambda s: s.value_counts().index[0]).reindex(g.index).fillna("none")
    g["attack"] = atk.to_numpy()
    g["attack_type"] = typ.to_numpy()
    # rule flags per cell (any flagged frame in the cell), for the hybrid
    g["rule_flag"] = d.groupby("cell")["rule_flag"].max().reindex(g.index).fillna(False).to_numpy()
    g["t_s"] = g.index.to_numpy() * GRID_S
    return g.reset_index(drop=True)


def windows(g: pd.DataFrame):
    """Sliding 1 s windows (hop 0.1 s) -> features, labels, end times."""
    X = g[SIGNALS].to_numpy(dtype=np.float64)
    n = len(X) - WIN + 1
    if n <= 0:
        return np.zeros((0, len(FEATURES))), np.zeros(0, int), np.array([], dtype=object), np.zeros(0), np.zeros(0, bool)
    idx = np.arange(0, n, HOP)
    # strided view of windows: (n, WIN, 4)
    sh = (n, WIN, X.shape[1])
    st = (X.strides[0], X.strides[0], X.strides[1])
    W = np.lib.stride_tricks.as_strided(X, shape=sh, strides=st)[idx]
    mean = W.mean(axis=1)
    # log spread: a frozen signal (std exactly 0) becomes an extreme value instead
    # of sitting inside the normal range after standardisation
    std = np.log10(W.std(axis=1) + STD_EPS)
    chg = W[:, -1, :] - W[:, 0, :]
    F = np.concatenate([np.stack([mean[:, i], std[:, i], chg[:, i]], axis=1)
                        for i in range(X.shape[1])], axis=1)

    def _win(a):
        return np.lib.stride_tricks.as_strided(a, shape=(n, WIN), strides=(a.strides[0], a.strides[0]))[idx]

    atk = np.ascontiguousarray(g["attack"].to_numpy(dtype=np.int64))
    types = ["none", "flood", "injection", "masquerade", "replay", "freeze"]
    code = np.ascontiguousarray(pd.Categorical(g["attack_type"], categories=types).codes.astype(np.int64))
    rf = np.ascontiguousarray(g["rule_flag"].to_numpy(dtype=np.int64))
    end = idx + WIN - 1
    y = _win(atk).max(axis=1)
    # episodes are at least 20 s apart, so a window holds at most one family
    ytype = np.array(types, dtype=object)[_win(code).max(axis=1)]
    rule_w = _win(rf).max(axis=1).astype(bool)
    return F, y, ytype, g["t_s"].to_numpy()[end], rule_w


def model_score(Z: np.ndarray, mlp, in_idx, out_idx) -> np.ndarray:
    """Score in float64 via scikit-learn: squared residual (regressor) or MSE (AE)."""
    pred = mlp.predict(Z[:, in_idx])
    if out_idx >= 0:
        return (pred - Z[:, out_idx]) ** 2
    return ((pred - Z) ** 2).mean(axis=1)


def _mlp(hidden):
    return MLPRegressor(hidden_layer_sizes=hidden, activation="relu", solver="adam",
                        learning_rate_init=1e-3, max_iter=1000, batch_size=256,
                        random_state=SEED, tol=1e-7, n_iter_no_change=30,
                        early_stopping=True, validation_fraction=0.1)


def fit_models(Xtr: np.ndarray):
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
    Z = (Xtr - mu) / sd
    all_idx = list(range(len(FEATURES)))
    ae = _mlp((6, 3, 6)).fit(Z, Z)
    print(f"  AE stopped after {ae.n_iter_} epochs, validation score {ae.best_validation_score_:.4f}")
    spr_in = [FEATURES.index(f) for f in SPR_IN]
    spr_out = FEATURES.index(SPR_OUT)
    spr = _mlp((8, 8)).fit(Z[:, spr_in], Z[:, spr_out])
    print(f"  SPR stopped after {spr.n_iter_} epochs, validation score {spr.best_validation_score_:.4f}")
    return {"mu": mu, "sd": sd,
            "ae": {"mlp": ae, "in": all_idx, "out": -1, "layers": [12, 6, 3, 6, 12]},
            "spr": {"mlp": spr, "in": spr_in, "out": spr_out, "layers": [len(spr_in), 8, 8, 1]}}


def scores(M, X: np.ndarray):
    Z = (X - M["mu"]) / M["sd"]
    return {k: model_score(Z, M[k]["mlp"], M[k]["in"], M[k]["out"]) for k in ("ae", "spr")}


def n_params(mlp) -> int:
    return int(sum(w.size for w in mlp.coefs_) + sum(b.size for b in mlp.intercepts_))


def episode_eval(ev: pd.DataFrame, field_windows: dict, flag_key: str):
    """Episode detected if any window ending inside [start, end + 1 s] is flagged.
    Latency = first flagged window end - episode start (window granularity)."""
    out = {}
    for _, e in ev.iterrows():
        W = field_windows[e["field"]]
        t = W["t_end"]
        m = (t >= e["t_start"]) & (t <= e["t_end"] + 1.0) & (W["ytype"] == e["attack_type"])
        f = W[flag_key] & m
        det = bool(f.any())
        lat = float(t[f].min() - e["t_start"]) if det else None
        out.setdefault(e["attack_type"], []).append((det, lat))
    res = {}
    for fam, lst in out.items():
        lats = [l for d, l in lst if d]
        res[fam] = {"episodes": len(lst), "detected": int(sum(d for d, _ in lst)),
                    "median_latency_ms": round(1000 * float(np.median(lats)), 1) if lats else None}
    return res


def main():
    t0 = time.perf_counter()
    norm, atk = C.DATASET_DIR / "normal", C.DATASET_DIR / "attacked"
    print("learning Phase 1 rules from clean fields ...")
    rules = B.learn_rules([norm / f"{f}.parquet" for f in B.TRAIN_FIELDS])

    print("building clean windows (train fields 1-5, threshold field 6) ...")
    Xtr = []
    for f in TRAIN_FIELDS:
        F, y, _, _, _ = windows(signal_grid(pd.read_parquet(norm / f"{f}.parquet"), rules))
        Xtr.append(F)
    Xtr = np.vstack(Xtr)
    Xth, _, _, _, _ = windows(signal_grid(pd.read_parquet(norm / f"{THRESH_FIELD}.parquet"), rules))
    print(f"  train windows {len(Xtr)}, threshold windows {len(Xth)}")

    print("training SPR and AE models ...")
    M = fit_models(Xtr)
    s_th = scores(M, Xth)
    thr = {k: float(np.quantile(s_th[k], 1 - FPR_TARGET)) for k in ("ae", "spr")}
    for k in ("spr", "ae"):
        print(f"  {k.upper()} params {n_params(M[k]['mlp'])}, threshold {thr[k]:.4f} "
              f"(clean {1-FPR_TARGET:.1%} quantile)")

    print("evaluating on attacked fields 7-10 ...")
    field_windows = {}
    parts = []
    Xtest = []
    for f in TEST_FIELDS:
        F, y, ytype, t_end, rule_w = windows(signal_grid(pd.read_parquet(atk / f"{f}.parquet"), rules))
        Xtest.append(F)
        s = scores(M, F)
        W = pd.DataFrame({"t_end": t_end, "y": y, "ytype": ytype, "rule": rule_w,
                          "ae": s["ae"] > thr["ae"], "spr": s["spr"] > thr["spr"]})
        W["hyb_ae"] = W["rule"] | W["ae"]
        W["hyb_spr"] = W["rule"] | W["spr"]
        W["field"] = f
        field_windows[f] = W
        parts.append(W)
    T = pd.concat(parts, ignore_index=True)
    y = T["y"].to_numpy().astype(bool)

    res = {
        "windows": {"length_s": WIN * GRID_S, "hop_s": HOP * GRID_S, "features": FEATURES,
                    "std_transform": f"log10(std + {STD_EPS})",
                    "n_train": int(len(Xtr)), "n_threshold": int(len(Xth)),
                    "n_test": int(len(T)), "n_test_attacked": int(y.sum())},
        "models": {k: {"layers": M[k]["layers"], "params": n_params(M[k]["mlp"]),
                       "inputs": [FEATURES[i] for i in M[k]["in"]],
                       "target": FEATURES[M[k]["out"]] if M[k]["out"] >= 0 else "reconstruction",
                       "threshold": round(thr[k], 6)} for k in ("spr", "ae")},
        "exported_model": "spr",
        "fpr_target_clean_quantile": FPR_TARGET,
        "window_level": {k: B.metrics(y, T[k].to_numpy()) for k in MODELS},
        "per_family": {},
        "event_detection": {},
    }
    for fam, g in T[T["y"] == 1].groupby("ytype"):
        res["per_family"][fam] = {"n_windows": int(len(g)),
                                  **{k: round(float(g[k].mean()), 4) for k in MODELS}}
    ev = pd.read_csv(C.DATASET_DIR / "events.csv")
    for k in MODELS:
        res["event_detection"][k] = episode_eval(ev, field_windows, k)
    res["runtime_s"] = round(time.perf_counter() - t0, 1)

    C.RESULTS_DIR.mkdir(exist_ok=True)
    (C.RESULTS_DIR / "metrics_phase2.json").write_text(json.dumps(res, indent=2))
    save = {"mu": M["mu"], "sd": M["sd"], "features": np.array(FEATURES),
            "std_eps": STD_EPS, "exported": "spr"}
    for k in ("ae", "spr"):
        mlp = M[k]["mlp"]
        save[f"{k}_thr"] = thr[k]
        save[f"{k}_in"] = np.array(M[k]["in"])
        save[f"{k}_out"] = M[k]["out"]
        for i, w in enumerate(mlp.coefs_):
            save[f"{k}_W{i}"] = w
        for i, b in enumerate(mlp.intercepts_):
            save[f"{k}_b{i}"] = b
    np.savez(C.RESULTS_DIR / "tiny_model.npz", **save)
    T.to_parquet(C.RESULTS_DIR / "test_windows_phase2.parquet", index=False)
    # raw (unstandardised) test features for export_embedded.py (untracked, ~40 MB)
    np.save(C.RESULTS_DIR / "test_features_phase2.npy", np.vstack(Xtest).astype(np.float32))

    print(json.dumps(res["window_level"], indent=2))
    print("\nper-family window recall:\n", json.dumps(res["per_family"], indent=2))
    print("\nepisode detection:\n", json.dumps(res["event_detection"], indent=2))
    make_figure(res)


def make_figure(res):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fams = ["flood", "injection", "masquerade", "replay", "freeze"]
    fams = [f for f in fams if f in res["per_family"]]
    keys = [("rule", "Rules (Phase 1)", "#2b6cb0"), ("ae", "Tiny AE (variant)", "#dd6b20"),
            ("spr", "Spread model (exported)", "#805ad5"), ("hyb_spr", "Hybrid rules + spread", "#2f855a")]
    x = np.arange(len(fams)); w = 0.2
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    for j, (k, lab, col) in enumerate(keys):
        ax.bar(x + (j - 1.5) * w, [res["per_family"][f][k] for f in fams], w, label=lab, color=col)
    ax.set_xticks(x); ax.set_xticklabels(fams, rotation=15)
    ax.set_ylabel("Attacked-window detection rate")
    ax.set_ylim(0, 1.05)
    ax.set_title("AgriSecure-AI Phase 2 - window-level detection by attack family")
    ax.legend(fontsize=8); ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    d = C.RESULTS_DIR / "figures"; d.mkdir(exist_ok=True)
    fig.savefig(d / "phase2_detection_by_family.png", dpi=140)
    print(f"\nfigure -> {d / 'phase2_detection_by_family.png'}")


if __name__ == "__main__":
    main()
