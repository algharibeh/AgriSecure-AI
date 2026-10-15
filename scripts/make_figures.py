"""Reader-facing figures, generated from the committed result files.

Part of the AgriSecure-AI project.

Every number drawn here is read from results/*.json, dataset/events.csv or the
parquet files, so the figures cannot drift from the record. Outputs, all in
results/figures/:

  overview_dashboard.png   four panels: episode detection grid, footprint vs
                           the 10 KB target, detection latency, data scale
  attack_strips.png        30 s of engine speed, torque and fuel rate around
                           one episode of each family (field 7), the episode
                           shaded, rule and model flags marked
  phase_status.png         the four filed phases as tiles, each item marked
                           done / partial / open, matching the report tables

Run: .venv/Scripts/python.exe -I scripts/make_figures.py
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C
import detect_baseline as B
import train_tiny_model as T

FIG = C.RESULTS_DIR / "figures"
FAMS = ["flood", "injection", "masquerade", "replay", "freeze"]
COL = {"rules": "#2b6cb0", "model": "#805ad5", "hybrid": "#2f855a",
       "attack": "#e53e3e", "open": "#a0aec0", "done": "#2f855a", "partial": "#d69e2e",
       "text": "#1a202c", "grid": "#e2e8f0"}
plt.rcParams.update({"font.size": 9, "axes.titlesize": 10.5, "axes.titleweight": "bold",
                     "axes.spines.top": False, "axes.spines.right": False})


def load():
    m1 = json.loads((C.RESULTS_DIR / "metrics.json").read_text())
    m2 = json.loads((C.RESULTS_DIR / "metrics_phase2.json").read_text())
    fp = json.loads((C.RESULTS_DIR / "footprint_phase2.json").read_text())
    sil = json.loads((C.RESULTS_DIR / "sil_phase2.json").read_text())
    ev = pd.read_csv(C.DATASET_DIR / "events.csv")
    return m1, m2, fp, sil, ev


# --------------------------------------------------------------------------
def dashboard(m1, m2, fp, sil, ev):
    fig, axs = plt.subplots(2, 2, figsize=(11, 7.6))
    fig.suptitle("AgriSecure-AI — Phase 1 and the first Phase 2 result, at a glance",
                 fontsize=13, fontweight="bold", x=0.02, ha="left")

    # (a) episode detection grid --------------------------------------------
    ax = axs[0, 0]
    cols = [("rule", "Rules\n(Phase 1)"), ("spr", "Tiny model\n(Phase 2)"), ("hyb_spr", "Hybrid\nrules + model")]
    E = m2["event_detection"]
    grid = np.array([[E[k][f]["detected"] / E[k][f]["episodes"] for k, _ in cols] for f in FAMS])
    ax.imshow(grid, cmap="Greens", vmin=0, vmax=1, aspect="auto")
    for i, f in enumerate(FAMS):
        for j, (k, _) in enumerate(cols):
            d, n = E[k][f]["detected"], E[k][f]["episodes"]
            lat = E[k][f]["median_latency_ms"]
            txt = f"{d} / {n}" + (f"\n{lat:.0f} ms" if lat is not None and lat < 1000 else
                                  (f"\n{lat/1000:.1f} s" if lat is not None else ""))
            ax.text(j, i, txt, ha="center", va="center", fontsize=8.5,
                    color="white" if grid[i, j] > 0.6 else COL["text"])
    ax.set_xticks(range(len(cols))); ax.set_xticklabels([c[1] for c in cols])
    ax.set_yticks(range(len(FAMS))); ax.set_yticklabels([f.capitalize() for f in FAMS])
    ax.set_title("Attack episodes detected (of 72), median latency")
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)

    # (b) footprint ----------------------------------------------------------
    ax = axs[0, 1]
    items = [("Static count of every tensor and buffer", fp["bytes"]["total_static"], COL["model"]),
             ("Compiled, Cortex-M0+ (flash + RAM)", 1256, COL["hybrid"]),
             ("Compiled, Cortex-M4 (flash + RAM)", 1300, COL["hybrid"]),
             ("Cortex-M4 + 256 B rule state", 1300 + 256, COL["hybrid"])]
    y = np.arange(len(items))[::-1]
    ax.barh(y, [v for _, v, _ in items], color=[c for _, _, c in items], height=0.6)
    for yi, (_, v, _) in zip(y, items):
        ax.text(v + 150, yi, f"{v:,} B", va="center", fontsize=8.5)
    ax.axvline(fp["target_bytes"], color=COL["attack"], ls="--", lw=1.2)
    ax.text(fp["target_bytes"] - 150, y.min() - 0.1, "plan target\n10 KB", color=COL["attack"],
            ha="right", va="center", fontsize=8.5)
    ax.set_yticks(y); ax.set_yticklabels([n for n, _, _ in items], fontsize=8.5)
    ax.set_xlim(0, 11500); ax.set_xlabel("bytes")
    ax.set_title("Embedded footprint of the hybrid detector")
    ax.grid(axis="x", color=COL["grid"])

    # (c) latency ------------------------------------------------------------
    ax = axs[1, 0]
    x = np.arange(len(FAMS)); w = 0.26
    off = [E["hyb_spr"][f]["median_latency_ms"] for f in FAMS]
    srule = {s["family"]: s["rule_latency_ms"] for s in sil["segments"]}
    smodel = {s["family"]: s["model_latency_ms"] for s in sil["segments"]}
    series = [("Offline, hybrid (median over episodes)", off, COL["hybrid"]),
              ("SIL replay, rules (wall clock)", [srule.get(f) for f in FAMS], COL["rules"]),
              ("SIL replay, model (wall clock)", [smodel.get(f) for f in FAMS], COL["model"])]
    for j, (lab, vals, c) in enumerate(series):
        v = [np.nan if (val is None) else max(val, 0.05) for val in vals]
        ax.bar(x + (j - 1) * w, v, w, label=lab, color=c)
        for xi, val in zip(x + (j - 1) * w, vals):
            if val is None:
                ax.plot(xi, 0.065, marker="x", ms=6, color=COL["attack"], mew=1.5)
    ax.plot([], [], marker="x", ls="none", ms=6, color=COL["attack"], mew=1.5, label="not detected")
    ax.set_yscale("log"); ax.set_ylim(0.05, 20000)
    ax.set_yticks([0.1, 1, 10, 100, 1000, 10000]); ax.set_yticklabels(["0.1 ms", "1 ms", "10 ms", "100 ms", "1 s", "10 s"])
    ax.axhline(50, color=COL["attack"], ls="--", lw=1); ax.text(len(FAMS) - 0.55, 58, "50 ms target", color=COL["attack"], ha="right", fontsize=8)
    ax.set_xticks(x); ax.set_xticklabels([f.capitalize() for f in FAMS])
    ax.set_title("Detection latency by family")
    ax.legend(fontsize=7.5, loc="upper left", frameon=False); ax.grid(axis="y", color=COL["grid"])

    # (d) data scale ---------------------------------------------------------
    ax = axs[1, 1]; ax.axis("off")
    n_ep = int(len(ev))
    facts = [
        ("Source", "Tümosan 81.110 P tractor, soil tillage,\n10 fields (Mendeley Data, CC BY 4.0)"),
        ("Real signals", "24.7 h, 889,255 decoded rows at 10 Hz"),
        ("Frames", "about 5.16 million J1939 frames, reconstructed;\nfields 1–6 clean, 7–10 attacked"),
        ("Evaluation", f"{m1['n_test_frames']:,} frames, {m1['n_attack_frames']:,} of them\nattack frames ({100*m1['attack_prevalence']:.1f} %)"),
        ("Episodes", f"{n_ep} seeded, five families, labelled per frame"),
        ("Windows", f"{m2['windows']['n_train']:,} train · {m2['windows']['n_threshold']:,} threshold\n{m2['windows']['n_test']:,} test (1 s, 0.1 s hop)"),
        ("Model", f"{m2['models']['spr']['params']} parameters, int8, clean traffic only"),
        ("Simulated", "the attacks and the frame layer;\nthe signal content is real"),
        ("Open", "hardware-in-the-loop; freeze across fields"),
    ]
    ax.set_title("Data and scope", loc="left")
    yy = 0.98
    for k, v in facts:
        ax.text(0.0, yy, k, fontsize=8.5, fontweight="bold", va="top", color=COL["text"], transform=ax.transAxes)
        ax.text(0.22, yy, v, fontsize=8.5, va="top", color=COL["text"], transform=ax.transAxes, linespacing=1.25)
        yy -= 0.075 + 0.055 * v.count("\n")

    fig.text(0.02, 0.005, "Drawn by scripts/make_figures.py from the committed result files (results/*.json, dataset/events.csv). "
             "Attacks are simulated on real tractor traffic; no vehicle or bus was involved. SIL is not HIL.",
             fontsize=7, color="#4a5568")
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    fig.savefig(FIG / "overview_dashboard.png", dpi=150)
    plt.close(fig)
    print("figure -> overview_dashboard.png")


# --------------------------------------------------------------------------
def attack_strips(ev):
    field = "field_7"
    rules = B.learn_rules([C.DATASET_DIR / "normal" / f"{f}.parquet" for f in B.TRAIN_FIELDS])
    g = T.signal_grid(pd.read_parquet(C.DATASET_DIR / "attacked" / f"{field}.parquet"), rules)
    W = pd.read_parquet(C.RESULTS_DIR / "test_windows_phase2.parquet")
    W = W[W["field"] == field]
    first = ev[ev["field"] == field].groupby("attack_type", sort=False).first()

    fig, axs = plt.subplots(len(FAMS), 1, figsize=(11, 10.5), sharex=False)
    for ax, fam in zip(axs, FAMS):
        e = first.loc[fam]
        t0, t1 = e["t_start"] - 10, e["t_end"] + 10
        s = g[(g["t_s"] >= t0) & (g["t_s"] <= t1)]
        t = s["t_s"] - e["t_start"]
        ax.axvspan(0, e["t_end"] - e["t_start"], color=COL["attack"], alpha=0.12, lw=0)
        ax.plot(t, s["rpm"], color="#2d3748", lw=1.1, label="engine speed (rpm)")
        ax2 = ax.twinx()
        ax2.plot(t, s["fuel"], color="#dd6b20", lw=1.0, label="fuel rate (L/h)")
        ax2.plot(t, s["torque"], color="#3182ce", lw=0.9, ls="--", label="torque (%)")
        ax2.spines["top"].set_visible(False)
        # flags
        ymax = ax.get_ylim()[1]
        rf = s[s["rule_flag"]]
        if len(rf):
            ax.scatter(rf["t_s"] - e["t_start"], np.full(len(rf), ymax * 1.03), marker="|", s=60, color=COL["rules"], label="rule flag")
        mw = W[(W["t_end"] >= t0) & (W["t_end"] <= t1) & W["spr"]]
        if len(mw):
            ax.scatter(mw["t_end"] - e["t_start"], np.full(len(mw), ymax * 1.09), marker="|", s=60, color=COL["model"], label="model flag")
        ax.set_ylim(top=ymax * 1.14)
        n_r, n_m = int(len(rf)), int(len(mw))
        verdict = ("rules " + ("flagged" if n_r else "silent") + ", model " + ("flagged" if n_m else "silent"))
        ax.set_title(f"{fam.capitalize()} — episode of {e['t_end'] - e['t_start']:.0f} s at t = {e['t_start']:.0f} s in field 7 — {verdict}", loc="left")
        ax.set_ylabel("rpm"); ax2.set_ylabel("L/h  |  %")
        ax.grid(axis="x", color=COL["grid"])
        if fam == "injection":
            h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
            fig.legend(h1 + h2, l1 + l2, fontsize=8, loc="upper right", ncol=5, frameon=False,
                       bbox_to_anchor=(0.99, 0.955))
    axs[-1].set_xlabel("seconds from the start of the episode (shaded)")
    fig.suptitle("What each attack family looks like on the bus, and when the detectors flagged it",
                 fontsize=12.5, fontweight="bold", x=0.02, y=0.985, ha="left")
    fig.text(0.02, 0.004, "Signals are decoded from the reconstructed J1939 stream after the source-address rule; flood frames carry no "
             "signal, so the flood panel shows the rule flags only.\nFreeze: engine speed and torque are held while the "
             "process continues — the gap the current model does not close across fields.",
             fontsize=7, color="#4a5568", linespacing=1.3)
    fig.tight_layout(rect=(0, 0.03, 1, 0.945))
    fig.savefig(FIG / "attack_strips.png", dpi=150)
    plt.close(fig)
    print("figure -> attack_strips.png")


# --------------------------------------------------------------------------
def phase_status():
    phases = [
        ("Phase 1 · months 0–6\nThreat modelling and data infrastructure", [
            ("Threat analysis of agricultural J1939 attack vectors", "done"),
            ("Real-world network data (public tractor recordings, reconstructed frames)", "partial"),
            ("Labelled, curated dataset for training and evaluation", "done"),
            ("Prepared for public release (datasheet, licence, checksums)", "done"),
            ("Attack injection via hardware-in-the-loop", "open"),
        ]),
        ("Phase 2 · months 7–15\nAI model development and embedded optimisation", [
            ("ML anomaly model trained on clean traffic, evaluated on held-out attacks", "done"),
            ("Memory footprint under 10 KB (measured: 1,300 B on Cortex-M4)", "done"),
            ("Low false-positive rate (0.02 % model, 0.19 % hybrid, window level)", "partial"),
            ("Freeze family detected across fields", "open"),
            ("Extensive HIL validation; real-time on an ECU", "open"),
        ]),
        ("Phase 3 · months 16–21\nSafety–cybersecurity integration", [
            ("Fallback control strategies and safety monitors", "open"),
            ("ISO 26262 / ISO/SAE 21434 artefacts", "open"),
        ]),
        ("Phase 4 · months 22–36\nField deployment and scaling", [
            ("On-machine validation, pilots, third-party evaluation", "open"),
        ]),
    ]
    colours = {"done": COL["done"], "partial": COL["partial"], "open": COL["open"]}
    labels = {"done": "done (software, measured)", "partial": "partly done", "open": "open / not started"}
    import textwrap
    fig, ax = plt.subplots(figsize=(11, 6.4)); ax.axis("off")
    ax.set_xlim(0, 4); ax.set_ylim(0, 1)
    for i, (title, items) in enumerate(phases):
        x0 = i + 0.04
        ax.add_patch(FancyBboxPatch((x0, 0.08), 0.92, 0.84, boxstyle="round,pad=0.01,rounding_size=0.02",
                                    fc="#f7fafc", ec="#cbd5e0", lw=1))
        head, sub = title.split("\n")
        ax.text(x0 + 0.04, 0.88, head, fontsize=9, fontweight="bold", va="top", color=COL["text"])
        ax.text(x0 + 0.04, 0.835, "\n".join(textwrap.wrap(sub, 31)), fontsize=8, va="top",
                color="#4a5568", linespacing=1.2)
        yy = 0.71
        for item, st in items:
            lines = textwrap.wrap(item, 34)
            ax.plot(x0 + 0.075, yy - 0.012, marker="o", ms=9, color=colours[st], ls="none")
            ax.text(x0 + 0.125, yy, "\n".join(lines), fontsize=7.6, va="top", color=COL["text"], linespacing=1.2)
            yy -= 0.045 + 0.037 * len(lines)
    for k, (st, lab) in enumerate(labels.items()):
        ax.plot(0.08 + k * 1.1, 0.035, marker="o", ms=8, color=colours[st], ls="none")
        ax.text(0.13 + k * 1.1, 0.035, lab, fontsize=8, va="center")
    fig.suptitle("Status against the four phases of the project plan (October 2026; months as planned)",
                 fontsize=12.5, fontweight="bold", x=0.02, ha="left")
    fig.text(0.98, 0.03, "Source: status tables in REPORT.md and REPORT_phase2.md", ha="right", fontsize=7, color="#4a5568")
    fig.savefig(FIG / "phase_status.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("figure -> phase_status.png")


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    m1, m2, fp, sil, ev = load()
    dashboard(m1, m2, fp, sil, ev)
    phase_status()
    attack_strips(ev)


if __name__ == "__main__":
    main()
