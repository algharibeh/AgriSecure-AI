# AgriSecure-AI Phase 1 — threat model, dataset, and baseline detection

Part of the AgriSecure-AI project.

## Summary

Phase 1 establishes the groundwork for on-board intrusion detection on
agricultural CAN / SAE J1939 networks: a threat model, a labelled dataset that
fills a real gap in the public record, and a baseline detector with measured
results. Everything runs in software on a single PC; no vehicle, no hardware bus,
and no attack against any real system are involved. The one Phase 1 objective that
needs hardware, hardware-in-the-loop validation, is left open and named as such.

The headline measured result: a lightweight rule-based detector, learning only
from attack-free traffic, detects every flood, injection, and masquerade episode
within about a millisecond and most replay episodes within about 44 ms, at an
overall false-positive rate of 0.05 %. Stuck-value (freeze) attacks are not caught
by the baseline, for a reason that is itself a finding and a Phase 2 motivation.

## What was built

1. **Threat model** (`docs/THREAT_MODEL.md`): an ISO/SAE 21434-style analysis of a
   tractor J1939 / ISOBUS network — assets, entry points, five attack families,
   qualitative risk, and the safety link to ISO 26262.
2. **Dataset** (`docs/DATASET_DATASHEET.md`): real tractor signals reconstructed
   into a standards-conformant J1939 frame stream, with seeded, labelled anomaly
   scenarios. Normal content is real; the frame layer is a documented, lossless
   reconstruction; the anomalies are simulated.
3. **Baseline detectors** (`scripts/detect_baseline.py`): a rule-based IDS and an
   Isolation Forest, both trained on attack-free fields and evaluated on held-out
   attacked fields.

## Data

Real traffic comes from a Tümosan 81.110 P tractor during soil tillage
(Mendeley DOI 10.17632/bbjtjrsxvx.2, CC BY 4.0): 24.7 hours, 889,255 decoded
signal rows at 10 Hz across ten fields. These signals are packed back into their
standard J1939 parameter groups at standard transmission periods, giving about
5.16 million CAN frames. Payload packing is lossless to SPN resolution, verified by
round-trip decode. Fields 1–6 are kept attack-free for training; fields 7–10
(about 2.26 million frames) receive injected attacks for evaluation.

No public dataset carried agricultural J1939 traffic with labelled attacks before
this: the published J1939 attack datasets are from trucks, and the agricultural
datasets contain normal operation only. This dataset closes that gap.

## Detectors

**Rule-based IDS** — learns, from clean traffic only: the set of source addresses
that transmit each PGN, each PGN's minimum normal inter-arrival time, and physical
range and rate-of-change envelopes per signal. It flags a frame whose address is
not the learned transmitter of its PGN, whose arrival is far faster than normal, or
whose decoded value is out of range or jumps impossibly. State per PGN is a handful
of numbers, which is the embedded-friendly path Phase 2 must fit.

**Isolation Forest** — an unsupervised model trained on standardised per-frame
features (PGN, address, priority, log inter-arrival, decoded value, value delta)
from clean traffic, flagging outliers in the attacked fields. Included as a
reference ML baseline.

## Results

Evaluation on the attacked fields (2,261,382 frames, 18,172 attack frames,
0.8 % prevalence).

| Detector | Precision | Recall | F1 | False-positive rate |
| --- | --- | --- | --- | --- |
| Rule-based IDS | 0.935 | 0.934 | 0.935 | 0.05 % |
| Isolation Forest | 0.103 | 0.109 | 0.106 | 0.77 % |

Per-family detection rate (fraction of that family's attack frames flagged):

| Family | Rule-based | Isolation Forest |
| --- | --- | --- |
| Flood (DoS) | 1.00 | 0.00 |
| Masquerade | 1.00 | 0.77 |
| Injection | 0.78 | 0.66 |
| Replay | 0.77 | 0.61 |
| Freeze | 0.00 | 0.00 |

Episode-level detection and latency (rule-based), where an episode counts as
detected if any of its frames is flagged:

| Family | Episodes detected | Median latency |
| --- | --- | --- |
| Flood | 16 / 16 | 0.2 ms |
| Injection | 16 / 16 | 0.1 ms |
| Masquerade | 16 / 16 | ~0 ms (first spoofed frame) |
| Replay | 10 / 12 | 44.3 ms |
| Freeze | 0 / 12 | — |

Per-frame rule processing cost was about 0.5 microseconds on this PC. That is not
an embedded benchmark, but it shows the rule logic is far inside the 50 ms system
budget; the per-PGN state is small enough to carry the embedded footprint goal into
Phase 2.

## Reading the results honestly

- **Structural attacks are easy for domain rules, hard for naive ML.** Flood and
  masquerade change the bus structure — an unexpected address, an impossible rate —
  which the rules catch completely and instantly. The Isolation Forest misses flood
  almost entirely: on categorical-like features (PGN, address) it rides the edge of
  the training distribution rather than isolating the point, a known limitation.
  This is why the lightweight rules, not the generic ML model, are the stronger
  baseline here.
- **Injection and replay are detected at the episode level but not every frame.**
  Within an injected burst, the frames flagged are those that arrive too fast or
  whose value jumps; a run of held false values in the middle can sit inside the
  physical envelope. Every injection episode and most replay episodes are still
  caught quickly. Two replay episodes during steady operation were missed because
  the replayed values stayed close to the live ones.
- **Freeze is the baseline's blind spot, by design.** A stuck engine-speed value is
  invisible to timing, address, and range rules, and a run-length rule cannot tell
  a short freeze from legitimate idling (engine speed is genuinely constant for tens
  of seconds at idle). Detecting it needs context- or model-based methods. This is a
  concrete, measured motivation for Phase 2, not a gap we hide.

## Reproducing

```
.venv/Scripts/python.exe -I scripts/build_can_stream.py     # signals -> frames
.venv/Scripts/python.exe -I scripts/inject_anomalies.py     # labelled attacks
.venv/Scripts/python.exe -I scripts/detect_baseline.py      # metrics + figure
```

Outputs land in `dataset/`, `results/metrics.json`, and
`results/figures/detection_by_family.png`. The raw tractor download is excluded
from version control; `AVAILABILITY.md` documents its source and licence.

## Status against the Phase 1 objectives

| Phase 1 objective | State |
| --- | --- |
| Threat analysis of agricultural J1939 attack vectors | Done |
| Data infrastructure and a labelled dataset for training/evaluation | Done (software; first agricultural J1939 set with labelled attacks) |
| Dataset prepared for future public release | Done (CC BY 4.0, datasheet) |
| Hardware-in-the-loop attack simulation | Open — needs a physical bus / HIL rig |

Phase 1 is complete in software and produces a real, reproducible, publishable
result. The remaining Phase 1 item is hardware-in-the-loop, which is hardware work.
