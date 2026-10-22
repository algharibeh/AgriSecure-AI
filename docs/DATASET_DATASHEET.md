# Dataset datasheet — AgriSecure-AI Phase 1

Part of the AgriSecure-AI project.

A labelled CAN / SAE J1939 dataset for agricultural intrusion-detection research:
real tractor signal content carried in a reconstructed J1939 frame stream, with
reproducible, simulated anomaly scenarios. It is built to fill a specific gap:
public J1939 attack datasets exist for trucks, and public agricultural datasets
exist without attacks, but we found no public dataset carrying agricultural
traffic with labelled attacks as of October 2026 (sources checked are listed in
`AVAILABILITY.md`).

## Provenance and honesty statement

- **Normal content is real.** Every normal frame's payload carries values recorded
  from a Tümosan 81.110 P tractor during real soil-tillage operation
  (Mendeley Data, DOI 10.17632/bbjtjrsxvx.2, CC BY 4.0). The source publishes
  decoded signal time series at 10 Hz, not raw CAN frames. The ten source files
  are included unchanged in `data/tumosan_raw/FIELD_FILES.zip`, with the authors'
  README, under the same CC BY 4.0 licence.
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

Only `events.csv` and the sample are in version control. The parquet files
(about 45 MB in total) are reproduced byte-for-byte by the scripts, because the
generator is seeded; they will be attached to the tagged release or deposited
with a DOI, and until then are available on request. Their SHA-256 checksums are
listed below so any copy can be verified against this commit.

Per-frame columns (candump-style; decoded values are recovered from `data_hex` via
`scripts/common.py`):

`t_s, can_id_hex, pgn, label, priority, source_addr, dlc, data_hex, attack, attack_type`

## Checksums (SHA-256)

As built from the scripts at this commit with `SEED = 20261015`.

| File | SHA-256 |
| --- | --- |
| `dataset/normal/field_1.parquet` | `b0e47fb97d4461e82dca069502af0856cda33b9794d13f8ea5b745dd84cee831` |
| `dataset/normal/field_2.parquet` | `27db82a77f64418e3566614ff8a180b78e2c124b1b08a4f06d83cd64d51a4060` |
| `dataset/normal/field_3.parquet` | `970aa90837236f89cc6e90f11decc3cb4500b95b918ca530c63880a765db53bc` |
| `dataset/normal/field_4.parquet` | `7f09b35a00e46bae9dcb853bee8cec2216fc78767487d016bb1db4d588edcd3a` |
| `dataset/normal/field_5.parquet` | `1577868bcf6d0aff0da71c27d381a0329fdc7a2f25785d72270b317629d32318` |
| `dataset/normal/field_6.parquet` | `6e9c1f4e97a03e21b958b377268977af09e16110d94a20c6bb57223671ac3893` |
| `dataset/normal/field_7.parquet` | `920f10f7eab7d292b0dc9f24d61f856d4d7c9ff757372a7116a75bbbc0a3b794` |
| `dataset/normal/field_8.parquet` | `b1a62b3b846ea13806e5f1a53b8fa117fdf7a3d91f0249378d54b2593be8165a` |
| `dataset/normal/field_9.parquet` | `7f5c5b3e7dab9f18f884b5cecfebbd4323ec1b57d725d99786c0b843a930cf29` |
| `dataset/normal/field_10.parquet` | `bdcc99a52df1a9d5846f0dae3dae839edc02eb696f84362bb63f7e56aff9e761` |
| `dataset/attacked/field_7.parquet` | `f45d9a3f2bcf7acdc2b7560d5b03991730c938eea6ca63b6e6152be30c39caac` |
| `dataset/attacked/field_8.parquet` | `6430583df9f7eae1da6cf9684c38fbd24a3f94b019a82117ee96ddd9f1f7ece7` |
| `dataset/attacked/field_9.parquet` | `356a4951ef78afa90c7071e2a34e1e70e4f0088e82bb2009e6839972c12a4d54` |
| `dataset/attacked/field_10.parquet` | `412a8fb85f2309f27a62f5e024027aeb42fb3b24e27368f89160d02bfe800a72` |

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
