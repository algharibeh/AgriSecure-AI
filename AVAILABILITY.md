# AgriSecure-AI — Phase 1 data & tooling availability check

Part of the AgriSecure-AI project.

Purpose: confirm, before building, that every input Phase 1 needs is publicly
reachable and licence-clear, so the phase can be completed in software and show
real results. Phase 1 as scoped here is an **anomaly-detection** study on
CAN / SAE J1939 agricultural traffic: threat model, a labelled dataset built by
layering reproducible anomaly scenarios onto real tractor traffic, and baseline
detector metrics. No attack is performed against any real system; anomalies are
generated in a software (virtual-bus) simulation.

## Verdict

Phase 1 can be completed end to end on this PC in software and produce publishable
results. The only Phase-1 item that cannot be done without hardware is
hardware-in-the-loop (HIL) validation; it stays open and is reported as such.

## Datasets checked

| Source | Content | Licence | Access | Role in Phase 1 |
| --- | --- | --- | --- | --- |
| Tümosan 81.110 (Mendeley, DOI 10.17632/bbjtjrsxvx.2) | Real tractor J1939 soil-tillage traffic, 24.7 h, ~889k samples @10 Hz, decoded signals | **CC BY 4.0** | Public API returns `FIELD_FILES.rar`, 8.51 MB, no login | **Core** real agricultural normal-behaviour base |
| Colorado State heavy-vehicle logs | Real truck J1939 candump logs (Kenworth T270, DD15) | Page terms; cite | Direct `.zip` links live (up to ~2 GB) | Optional cross-domain real traffic |
| Korea Univ. J1939DB-IDS (DOI 10.21227/sd9k-ct72) | Decoded J1939 + 11 labelled attack scenarios (trucks) | Not stated; citation required | Dropbox + IEEE DataPort | External comparison baseline only (not redistributed) |
| TUM 5-tractor (DOI 10.1016/j.dib.2025.111494) | 862 h real J1939 + ISOBUS, GNSS | CC (Data in Brief) | Elsevier/PMC behind browser check; host not yet pinned | Nice-to-have; not on critical path |

Key point: no public dataset contains **agricultural traffic with labelled
attacks**. Korea's labelled attacks are trucks; the tractor datasets are normal
operation only. Closing that gap with real tractor traffic plus reproducible,
simulated anomalies is Phase 1's actual contribution.

## Tooling (this PC, Windows 10, 16 GB)

- Python 3.9 at `C:\Program Files\Python39\python.exe`, pip 22.0.4 — OK.
- Needed, all pip-installable: `python-can`, `cantools`, `pandas`, `numpy`,
  `scikit-learn`, `matplotlib`. A fresh `.venv` will be created for this project.
- Notes: the bare `python` command is the broken Windows Store alias — use the
  full path or the venv. The Tümosan download is a `.rar`, so a `.rar` extractor
  (7-Zip or `rarfile` + `unrar`) is needed at build time.

## What Phase 1 will produce (software)

1. ISO/SAE 21434-style threat model of a tractor J1939 / ISOBUS bus.
2. Labelled dataset: real Tümosan traffic + seeded, reproducible anomaly
   scenarios (fabricated-frame, replay, flooding, timing-drift, address-conflict),
   packaged with a datasheet and CC BY 4.0 licence.
3. Baseline detector (rule-based + Isolation Forest) with per-class detection
   rate, false-positive rate and detection latency, limits stated.
4. Comparison against the Korea J1939 IDS dataset for external validity.

Honesty rule (carried from prior work): real numbers only, limits stated,
"simulated anomalies on real traffic" never presented as recorded attacks.
