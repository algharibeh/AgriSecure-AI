# AgriSecure-AI in two pages

Part of the AgriSecure-AI project. Written for a reader who is not an engineer.
Every number here is taken from a file in this repository, named in brackets.

## The problem

A modern tractor is a small network. Its engine controller, transmission, and
the implement behind it exchange messages over a bus called CAN, using a
dialect called SAE J1939. That bus was designed decades ago for reliability,
not security: messages carry no signature, so any device plugged into the bus,
or any compromised component on it, can send a message that looks exactly like
the engine controller's. A forged engine-speed, vehicle-speed or hitch command
can change what the machine does.

The usual answer in office networks, a firewall or a cloud check, does not fit:
the controllers are tiny, often with a few kilobytes of memory, and a field
machine may have no connectivity at all. The detector has to live inside the
machine and decide in tens of milliseconds.

## What was done

![Process](figures/process.svg)

1. **Real data, not invented.** A public dataset of a Tümosan tractor working
   ten fields of soil tillage, 24.7 hours in all, published under an open
   licence, provides the normal behaviour [docs/DATASET_DATASHEET.md].
2. **Rebuilt into bus messages.** The published data are decoded readings; they
   were packed back into the standard J1939 messages that carry them, about
   5.16 million frames, and checked to decode back exactly [REPORT.md].
3. **Attacks injected in simulation.** Five kinds of attack, defined by a threat
   analysis that follows the automotive cybersecurity standard ISO/SAE 21434,
   were added to four of the ten fields: a flood that jams the bus, injected
   false values, a device impersonating the engine controller, replayed old
   messages, and a sensor value frozen in place. Seventy-two episodes, every
   frame labelled. Nothing was done to any real machine [docs/THREAT_MODEL.md].
4. **A rule-based detector (Phase 1).** It learns from the clean fields only
   which device sends which message, how often, and what values are physically
   possible, then flags anything outside that. It catches four of the five kinds
   of attack within milliseconds, with a false alarm on one frame in two
   thousand [results/metrics.json].
5. **A tiny learned model (Phase 2, first result).** Trained on clean traffic
   only, it watches one second of engine speed, torque, fuel rate and wheel
   speed and flags windows that are inconsistent with how a diesel engine
   behaves. Combined with the rules, it adds detection inside sustained attacks
   [results/metrics_phase2.json].
6. **Shrunk to fit a controller.** The model's weights were reduced to 8-bit
   integers and the whole detector was written in plain C. Compiled for a
   Cortex-M4, the kind of processor in a machine controller, it needs 1,300
   bytes, with a 10 KB target in the plan. The C version was checked against
   the Python version on 64 test cases with no disagreement
   [results/embedded_build_phase2.txt].
7. **Replayed on a virtual bus.** Attacked traffic was played back at real speed
   over a simulated CAN bus with the detector listening; it flagged the attacks
   within 0.1 to 1.3 milliseconds of their first message
   [results/sil_phase2.json].

## What the results show

![Dashboard](../results/figures/overview_dashboard.png)

- Flood, injection, impersonation and replay: every episode detected, median
  latency about 50 milliseconds at the one-second window resolution, and under
  two milliseconds on the live replay.
- The frozen-sensor attack: still not detected across fields. The report
  explains why: a governed diesel also holds its speed constant for long
  stretches, and the relation between engine load and fuel flow shifts from
  one field to the next, so a one-second window is not enough context. This is
  stated as an open problem, not hidden [REPORT_phase2.md].
- The footprint: the one number the plan fixed in advance, under 10 KB, is met
  by a factor of six or more, measured by the compiler.

![Attack strips](../results/figures/attack_strips.png)

## What is not claimed

- No vehicle, physical bus or real system was touched. The attacks are
  simulated on real traffic. The frame layer is a documented reconstruction,
  not the manufacturer's original bytes.
- The C code was compiled for a microcontroller, not run on one. No timing on
  real hardware is claimed.
- Hardware-in-the-loop validation, listed in both Phase 1 and Phase 2 of the
  plan, has not been done. It needs a physical bus or test rig.
- One tractor model, one kind of field work, five attack families designed by
  the author. Anything beyond that is extrapolation.
- No users, no adoption, no deployment.

## Where the project stands

![Phase status](../results/figures/phase_status.png)

Phase 1 of the plan is done in software, with hardware-in-the-loop open. Phase 2
has its first result, started early on the Phase 1 data: the model exists, the
footprint is measured, the frozen-sensor family and hardware validation are
open. Phases 3 and 4 have not started.

## How to check

Every figure above is drawn by `scripts/make_figures.py` from the result files;
every result file is produced by a script in `scripts/` from the public data
with a fixed random seed, so the whole chain can be rerun. The datasheet lists
a checksum for every generated data file. The repository is version-controlled
with dated commits.
