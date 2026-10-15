# Dataset datasheet — AgriSecure-AI Phase 1

Part of the AgriSecure-AI project.

A labelled CAN / SAE J1939 dataset for agricultural intrusion-detection research:
real tractor signal content carried in a reconstructed J1939 frame stream, with
reproducible, simulated anomaly scenarios. It is built to fill a specific gap:
public J1939 attack datasets exist for trucks, and public agricultural datasets
exist without attacks, but no public dataset carries agricultural traffic with
labelled attacks.

## Provenance and honesty statement

- **Normal content is real.** Every normal frame's payload carries values recorded
  from a Tümosan 81.110 P tractor during real soil-tillage operation
  (Mendeley Data, DOI 10.17632/bbjtjrsxvx.2, CC BY 4.0). The source publishes
  decoded signal time series at 10 Hz, not raw CAN frames.
- **The frame layer is reconstructed.** Each recorded signal is placed back into
  the standard J1939-71 parameter group that carries it, at that group's standard
  transmission period, with the real value packed using the documented SPN
  resolution/offset. The reconstruction is lossless to SPN resolution (verified by
  round-trip decode). It is a faithful reconstruction, not a claim of
  byte-identical original OEM frames; the OEM raw frames were not published.
- **Anomalies are simulated.** All attack frames are injected into this simulated
  stream by a seeded generator. Nothing was done to any real vehicle or network.

## PGN / SPN mapping

| PGN | Label | Period | Source addr | Signals (SPN) |
| --- | --- | --- | --- | --- |
| 61444 | EEC1 | 100 ms | 0x00 engine | EngineSpeed (190), Actual % torque (513) |
| 65266 | LFE1 | 100 ms | 0x00 engine | Fuel rate (183) |
| 65265 | CCVS1 | 100 ms | 0x00 engine | Wheel-based vehicle speed (84) |
| 65262 | ET1 | 1000 ms | 0x00 engine | Coolant temp (110), oil temp (175) |
| 65263 | EFL/P1 | 500 ms | 0x00 engine | Oil pressure (100) |
| 65091 | PTO | 100 ms | 0x81 implement | PTO status |
| 65093 | RearHitch | 100 ms | 0x81 implement | Hitch position (1873) |
| 65280 | PROP_B_AUX | 200 ms | 0x21 body | Draft sensors, transfer case, keypad |

Deviations from the standard, chosen to carry the real recorded range losslessly
and documented here for transparency: rear-hitch position (SPN 1873, standard
0.4 %/bit over 0–100 %) and the draft sensors reach −126…128 %, so they use a
2-byte 0.1 %/bit field with a −200 offset. Exhaust after-treatment temperature in
the source is not mapped to a broadcast PGN. Unused payload bytes are the J1939
"not available" fill (0xFF).

## Files and schema

- `dataset/normal/field_{1..10}.parquet` — attack-free reconstructed streams.
- `dataset/attacked/field_{7..10}.parquet` — the same streams with injected,
  labelled anomalies (fields 1–6 are kept clean for detector training).
- `dataset/events.csv` — one row per injected episode: field, family, start, end,
  frame count.
- `dataset/SAMPLE_field7_attacked.csv` — a small human-readable excerpt.

Per-frame columns (candump-style; decoded values are recovered from `data_hex` via
`scripts/common.py`):

`t_s, can_id_hex, pgn, label, priority, source_addr, dlc, data_hex, attack, attack_type`

## Scale

- 10 fields, ~24.7 h of real tillage, 889,255 source signal rows.
- ~5.16 M reconstructed frames total; ~2.26 M in the attacked test fields.
- Attack prevalence in the test fields ≈ 0.8 % of frames.

## Attack families and parameters

Seeded (`SEED = 20261015`) so the dataset is byte-reproducible. Per test field:
flood ×4 (1 s), injection ×4 (5 s), masquerade ×4 (5 s), replay ×3 (4 s),
freeze ×3 (6 s). See `docs/THREAT_MODEL.md` for each family's mechanism.

## Intended use and limits

- For training and evaluating on-board intrusion detection for agricultural
  J1939 networks; the clean/attacked field split supports unsupervised setups.
- Not a substitute for hardware-in-the-loop or on-vehicle capture. The frame
  timing is reconstructed at standard periods, so sub-millisecond bus effects
  (arbitration jitter, error frames, bus load coupling) are idealised.
- One tractor model, tillage operation only. Attack realism is bounded by the
  families modelled here.

## Licence

Derivative of a CC BY 4.0 source; this dataset is released under **CC BY 4.0**.
Attribute both this project and the Tümosan source (DOI 10.17632/bbjtjrsxvx.2).
