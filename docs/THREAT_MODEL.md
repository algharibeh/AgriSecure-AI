# Threat model — agricultural CAN / SAE J1939 network

Part of the AgriSecure-AI project.

This is the Phase 1 threat analysis for the on-board network of an autonomous or
driver-assisted agricultural tractor and its implements. It follows the item
definition / threat-and-risk-assessment structure of ISO/SAE 21434 and names the
functional-safety link to ISO 26262 where a security failure becomes a safety
hazard. It defines the attack families that the Phase 1 dataset and detector
exercise.

## 1. Item definition

The item is the in-vehicle communication network of a tractor built on SAE J1939
(engine/driveline bus) and ISO 11783 / ISOBUS (tractor-implement bus). The buses
carry broadcast parameter groups (PGNs) that report and command engine speed and
torque, wheel speed, fuel rate, temperatures, rear-hitch position, PTO state, and
implement control. Each electronic control unit (ECU) transmits a defined set of
PGNs at defined periods from a defined source address (SA).

Relevant properties of the protocol:

- **No message authentication.** A CAN/J1939 frame carries no signature. Any node
  on the bus can transmit any arbitration ID, so a receiver cannot tell a genuine
  transmitter from an impostor.
- **No confidentiality.** Payloads are broadcast in clear and are decodable with
  public J1939-71 definitions.
- **Priority arbitration.** Lower arbitration IDs win the bus. A node emitting
  high-priority frames can starve legitimate traffic.
- **Address claiming.** Source addresses are claimed at run time (J1939-81), which
  a malicious node can abuse to impersonate or displace an ECU.

## 2. Assets and damage scenarios

| Asset | Security property | Damage scenario (safety link) |
| --- | --- | --- |
| Engine speed / torque command (EEC1) | Integrity, authenticity | Forged command changes engine output during field or road operation — loss of control (ISO 26262 hazard) |
| Wheel/vehicle speed (CCVS1) | Integrity | Falsified speed misleads guidance and speed-dependent implement logic |
| Rear hitch / implement control | Integrity, authenticity | Spurious raise/lower or implement actuation — property damage, bystander hazard |
| Bus availability | Availability | Flooding denies legitimate messages — safety functions miss their deadlines |
| Sensor broadcasts (temps, fuel, pressure) | Integrity | Masked fault or false reading — engine damage, unsafe continued operation |

## 3. Entry points (attack surface)

- Diagnostic connector (physical access, service tooling).
- Telematics / fleet gateway with a cellular or wireless link bridged to the bus.
- Implement connector: a connected implement or a malicious ISOBUS device.
- Aftermarket precision-agriculture or guidance hardware spliced into the bus.
- Supply-chain or firmware compromise of an on-bus ECU.

## 4. Attack families (threat scenarios)

These are the families reproduced in the Phase 1 dataset. Each is injected into a
reconstructed J1939 frame stream in simulation; none is performed against any real
device.

| Family | Mechanism on the bus | Primary observable |
| --- | --- | --- |
| **Flood (DoS)** | Burst of highest-priority frames from an unexpected address | Collapsed inter-arrival time; unknown PGN/address |
| **Injection (fabrication)** | Extra frames of a real PGN at elevated rate carrying implausible values, using the legitimate source address | Elevated rate; out-of-physics value / excessive rate-of-change |
| **Masquerade** | Frames of a real PGN sent from a foreign source address (impersonation / address abuse) | Two sources for one PGN; address not in the learned set |
| **Replay** | An earlier block of real frames re-sent later verbatim (stale values) | Doubled rate for the PGN; value inconsistent with current state |
| **Freeze (stuck value)** | An existing sensor PGN held at a constant payload (stuck/held sensor) | Value does not change while the process does |

In the terms used in the project plan: spoofing corresponds to the injection and
masquerade families; replay to replay; denial-of-service to flood; freeze is an
additional stuck-sensor family.

## 5. Risk rating (qualitative)

Rating combines impact (from the damage scenario) and attack feasibility
(from the entry points). Impact is highest where a forged message maps directly to
a motion or actuation command.

| Family | Impact | Feasibility | Risk |
| --- | --- | --- | --- |
| Injection of motion/actuation commands | High | Medium (needs bus access) | High |
| Masquerade of a control ECU | High | Medium | High |
| Flood / DoS | High (availability) | High (any on-bus node) | High |
| Replay | Medium | Medium | Medium |
| Freeze / stuck sensor | Medium–High | Medium | Medium–High |

## 6. Phase 1 security goals (verified by the dataset and baseline)

1. Detect a frame whose source address is not the learned transmitter of its PGN
   (masquerade, foreign-address flood).
2. Detect a PGN arriving far faster than its defined period (flood, injection,
   replay).
3. Detect a decoded signal outside its physical envelope or changing faster than
   physically possible (injection).
4. Do all of the above within a per-frame budget small enough for an embedded ECU
   and a detection latency under the 50 ms system target.

## 7. Known gap carried to Phase 2

Stuck-value (freeze) attacks are not reliably separable from legitimate
steady-state by timing, address, or physical-range rules alone, because engine and
vehicle signals are genuinely constant for long periods at idle. Detecting them
needs context- or model-based methods and is a Phase 2 objective, not a Phase 1
claim.
