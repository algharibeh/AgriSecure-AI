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

## Datasets checked (October 2026)

Sources used or considered for Phase 1. Checked in October 2026 from each
source's public page; "not verified" means the page did not state the item or it
could not be confirmed.

| Source | Content | Licence | Access | Role in Phase 1 |
| --- | --- | --- | --- | --- |
| Tümosan 81.110 (Mendeley, DOI 10.17632/bbjtjrsxvx.2) | Real tractor J1939 soil-tillage traffic, 24.7 h, ~889k samples @10 Hz, decoded signals | **CC BY 4.0** (stated in the archive's README) | Public API returns `FIELD_FILES.rar`, 8.51 MB, no login | **Core** real agricultural normal-behaviour base |
| Colorado State heavy-vehicle logs | Real truck J1939 candump logs (Kenworth T270, DD15) | Page terms; cite | Direct `.zip` links live (up to ~2 GB) | Optional cross-domain real traffic |
| Korea Univ. J1939DB-IDS (DOI 10.21227/sd9k-ct72) | Decoded J1939 + 11 labelled attack scenarios (trucks) | Not stated; citation required | Dropbox + IEEE DataPort | External comparison baseline only (not redistributed); deferred to Phase 2 |
| TUM 5-tractor (DOI 10.1016/j.dib.2025.111494) | 862 h real J1939 + ISOBUS, GNSS | CC BY 4.0 (Zenodo record) | Zenodo, DOI 10.5281/zenodo.14619787: five zip files, 2.8 GB, no login | Nice-to-have; not on critical path |

Survey of public CAN intrusion-detection datasets, to document the gap this
dataset is built to fill:

Each source was checked from its public page on the date shown. "Not stated" means the page names no licence or terms; "not verified" means the item could not be confirmed from the page.

| No. | Source and address | Agricultural? | J1939? | Labelled attacks? | Licence or terms | Notes | Checked |
|---|---|---|---|---|---|---|---|
| 1 | Tümosan 81.110 P tractor dataset, "Tumosan 81.110 Powershuttle soil tillage operations, Konya/Turkey" (Mendeley Data). https://doi.org/10.17632/bbjtjrsxvx.2 | Yes (one tractor, soil tillage, ten fields, about 24.7 hours) | Yes (decoded signals) | No | CC BY 4.0 | Normal operation only; ten tab-separated files, 889,255 samples | Oct 15 and Oct 18, 2026 |
| 2 | "Agricultural load cycles: tractor mission profiles from recorded GNSS and CAN bus data," Technical University of Munich, Data in Brief 60 (2025) 111494. Article https://doi.org/10.1016/j.dib.2025.111494; data https://doi.org/10.5281/zenodo.14619787 | Yes (five Fendt tractors, 77 to 240 kW, one season; 862 hours recorded, 354 hours of fieldwork on 143 fields published) | Yes (J1939 engine bus and ISOBUS, filtered by PGN and SPN) | No | CC BY 4.0 (Zenodo record) | Normal operation only; recording times hidden for anonymity | Oct 15 and Oct 18, 2026 |
| 3 | Colorado State University, "Heavy Vehicle CAN Data" (Prof. Jeremy Daily). https://www.engr.colostate.edu/~jdaily/J1939/candata.html | No (trucks: 2014 Kenworth T270, 2015 Kenworth T660, 2011 Freightliner Cascadia with a DD15 engine, 2019 International LT) | Yes | No | Not stated on the page | Real candump logs, including a cross-country trip of about 37.8 million messages and a 2014 crash test | Oct 15 and Oct 18, 2026 |
| 4 | J1939DB-IDS, "SAE J1939-decoded commercial vehicle signals for intrusion detection," Hwejae Lee and Huy Kang Kim, Korea University (IEEE DataPort). https://doi.org/10.21227/sd9k-ct72 | No (commercial vehicles: a 2011 Freightliner Cascadia, a 2014 Kenworth T270 and a simulator subset) | Yes | Yes (11 attack scenarios) | Not stated; download requires an IEEE DataPort account (subscription) | The only J1939 dataset with labelled attacks found | Oct 15 and Oct 18, 2026 |
| 5 | ROAD, Real ORNL Automotive Dynamometer CAN Intrusion Dataset, Oak Ridge National Laboratory. https://doi.org/10.5281/zenodo.10462796 (project page https://0xsam.com/road/) | No (one passenger vehicle on a dynamometer) | No (CAN 2.0) | Yes | CC BY 4.0 (Zenodo record) | Fuzzing and targeted fabrication attacks on a real car, plus simulated masquerade variants | Oct 15 and Oct 18, 2026 |
| 6 | HCRL Car-Hacking Dataset, Korea University Hacking and Countermeasure Research Lab. https://ocslab.hksecurity.net/Datasets/car-hacking-dataset | No (one passenger car, logged through the OBD-II port) | No | Yes | Not stated; released "for academic purposes" with a citation request | DoS, fuzzy, gear and RPM spoofing | Oct 15 and Oct 18, 2026 |
| 7 | HCRL Survival Analysis Dataset. https://ocslab.hksecurity.net/Datasets/survival-ids (also IEEE DataPort https://doi.org/10.21227/x6c9-aq71) | No (three passenger cars: Hyundai YF Sonata, Kia Soul, Chevrolet Spark) | No | Yes | Not stated; released "for academic purpose" with a citation request | Flooding, fuzzy, malfunction | Oct 15 and Oct 18, 2026 |
| 8 | SynCAN, Synthetic CAN Bus Data, ETAS. https://github.com/etas/SynCAN | No (synthetic) | No | Yes | Custom licence file: academic and non-academic use, non-commercial, not for field use | Signal-level synthetic CAN with plateau, continuous, playback, suppress and flooding attacks | Oct 15 and Oct 18, 2026 |
| 9 (added Oct 18) | OTIDS, CAN Intrusion Dataset, HCRL, Korea University. https://ocslab.hksecurity.net/Dataset/CAN-intrusion-dataset | No (one passenger car, Kia Soul, logged through the OBD-II port) | No | Yes | Not stated; released for academic purposes with a citation request | DoS, fuzzy and impersonation message injection | Oct 18, 2026 |
| 10 (added Oct 18) | CICIoV2024, Canadian Institute for Cybersecurity, University of New Brunswick. https://www.unb.ca/cic/datasets/iov-dataset-2024.html | No (one 2019 Ford passenger car, stationary, all ECUs connected) | No (CAN) | Yes (per-record label, category and class fields) | Not stated on the page | DoS and four spoofing attacks (gas, RPM, speed, steering wheel) | Oct 18, 2026 |
| 11 (added Oct 18) | can-train-and-test, Technical University of Denmark (Lampe and Meng, arXiv 2308.04972). https://bitbucket.org/brooke-lampe/can-train-and-test/src/master/ | No (four passenger vehicles: 2011 Chevrolet Impala, 2011 Chevrolet Traverse, 2016 Chevrolet Silverado, 2017 Subaru Forester) | No (CAN) | Yes (frame-level labels; nine attack types) | Not stated in the repository | Curated training and test splits for known and unknown vehicles and attacks | Oct 18, 2026 |
| 12 (added Oct 18) | "Investigating the implications of cyberattacks against precision agricultural equipment," Freyhof, Grispos, Pitla and Mahoney (University of Nebraska-Lincoln and University of Nebraska Omaha), ICCWS 2025; arXiv 2503.16283. https://arxiv.org/abs/2503.16283; https://papers.academic-conferences.org/index.php/iccws/article/view/3229 | Yes (a CAN bus-driven fertilizer applicator; a study, not a dataset) | Not stated on the pages (CAN bus) | No dataset: the abstract describes "a hypothetical case study, using real-world data"; neither page states that any logs or attack traffic were released | Paper: CC BY 4.0 (arXiv); CC BY-NC-ND 4.0 (proceedings) | The one U.S. academic study of attacks on an agricultural machine's network found; no data release found | Oct 18, 2026 |

Among the sources checked, no public dataset contains agricultural traffic with labelled attacks as of October 18, 2026. The labelled J1939 attacks that exist were recorded on trucks and are behind a subscription; the two tractor datasets contain normal operation only; the six passenger-car datasets use CAN 2.0 framing, not J1939's addressing, parameter groups and timing, and do not transfer to agricultural machinery; the one academic study of attacks on an agricultural machine's network released no traffic. This is a search of the sources listed, not an exhaustive survey.

Closing that gap with real tractor traffic plus reproducible, simulated anomalies is Phase 1's contribution.

## Tooling (this PC, Windows 10, 16 GB)

- Python 3.9 at `C:\Program Files\Python39\python.exe`, pip 22.0.4 — OK.
- Needed, all pip-installable: `python-can`, `cantools`, `pandas`, `numpy`,
  `scikit-learn`, `matplotlib`. A fresh `.venv` will be created for this project;
  the versions used are pinned in `requirements.txt`.
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
4. Comparison against the Korea J1939 IDS dataset for external validity —
   **deferred to Phase 2**; not part of the Phase 1 results in `REPORT.md`.

Honesty rule (carried from prior work): real numbers only, limits stated,
"simulated anomalies on real traffic" never presented as recorded attacks.
