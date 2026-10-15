# Changelog

## 0.1.0 — 2026-10-15

Phase 1, software groundwork.

- Threat model of a tractor J1939 / ISOBUS network (`docs/THREAT_MODEL.md`).
- Reconstruction of a J1939 frame stream from the public Tümosan tractor
  recordings (`scripts/build_can_stream.py`, `scripts/common.py`).
- Seeded injection of five labelled anomaly families into the test fields
  (`scripts/inject_anomalies.py`), with an episode list and a readable sample.
- Rule-based and Isolation Forest baselines with per-family and episode-level
  metrics and a figure (`scripts/detect_baseline.py`, `results/`).
- Dataset datasheet, availability check, and Phase 1 report.
- Fixed: `dataset/events.csv` now carries the injected frame count for every
  family (it was written as 0 for flood, injection, masquerade and replay).
- Added: `LICENSE` (MIT for code; dataset CC BY 4.0), `CITATION.cff`,
  `requirements.txt`, parquet checksums in the datasheet.

Hardware-in-the-loop validation and the comparison against the Korea
J1939DB-IDS truck dataset are open items carried to Phase 2.
