# Changelog

## 0.2.0 — unreleased (2026-10-15)

Phase 2, first result, started early on the Phase 1 data.

- Tiny context models on 1 s windows of the decoded engine and vehicle
  signals, trained on clean fields 1–5 with the threshold set on clean field 6
  (`scripts/train_tiny_model.py`): a spread-consistency model (exported) and
  an autoencoder (variant), evaluated alone and as a hybrid with the Phase 1
  rules. Freeze remains undetected across fields; the reason is measured.
- int8 export, C header and test vectors (`scripts/export_embedded.py`), and a
  dependency-free C99 reference detector with self-test
  (`embedded/tiny_ids.c`). Compiled size 1,300 B on Cortex-M4, 1,256 B on
  Cortex-M0+; build log in `results/embedded_build_phase2.txt`.
- Software-in-the-loop replay over a python-can virtual bus
  (`scripts/sil_replay.py`), results in `results/sil_phase2.json`.
- `reproduce.py`: one command that runs the Phase 1 and Phase 2 scripts in
  order, rebuilds the figures, runs the C self-test when a compiler is present,
  and compares the regenerated result files, headers, model, events list and
  parquet checksums with the record at this commit; writes a dated log to
  `results/` (ignored by git). README `Running it` updated.
- `REPORT_phase2.md`; README Phase 2 section.
- Reader-facing material: a process diagram (`docs/figures/process.svg`;
  the README's Mermaid copy of it was removed so the README prints as it is
  read on GitHub), three figures drawn from the result files by
  `scripts/make_figures.py` (overview dashboard, attack strips, phase status),
  a two-page explainer `docs/OVERVIEW.md`, and a README that opens with the
  plain-language summary, the diagram, the figures and a "where to look" table.

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
