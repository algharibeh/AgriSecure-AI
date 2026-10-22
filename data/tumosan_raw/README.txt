================================================================================
README

Real-World CAN Bus Dataset for Agricultural Tractor Block Load Cycle
Characterization
================================================================================

AUTHORS
--------------------------------------------------------------------------------
Aykut Dana (1) (*)
Orkun Ozener (2)
Ali Can Tellioglu (3)

(1) Test and Validation Department, Tumosan Teknoloji Muhendislik A.S.,
    Istanbul, Turkiye
(2) Department of Mechanical Engineering, Yildiz Technical University,
    Istanbul, Turkiye
(3) Test and Validation Department, Tumosan Teknoloji Muhendislik A.S.,
    Istanbul, Turkiye

Contact: aykut.dana@tumosanmuhendislik.com.tr


DESCRIPTION
--------------------------------------------------------------------------------
This dataset contains raw, high-resolution Controller Area Network (CAN) bus
recordings acquired from an agricultural tractor (Tumosan 81.110 P, rated
engine power 105 hp, maximum engine torque 450 Nm) during real-world soil
tillage operations on fields in the Konya Plain, Turkiye.

The tractor was instrumented with a custom-developed CAN-based telemetry
system with integrated GNSS positioning. The system streamed the data in
real time over a GSM/WebSocket link to a remote server, where raw CAN frames
were decoded into physical values using J1939 signal databases (.dbc/.xml)
and stored in a time-series database. The tractor was operated by genuine
farmers under real working conditions for approximately one year, spanning a
full agricultural cycle, and the recordings cover all activities of the
tractor (field work, road transport, idling).

From this roughly one-year campaign, the recordings were FILTERED down to the
in-field soil tillage segments, which impose the highest engine torque demand
among normal tractor operations. The segments were identified by jointly
considering the rear three-point hitch position (implement lowered/engaged
with the soil), the GNSS position (tractor inside a field), the vehicle speed
(typical tillage range ~4-12 km/h), and the engine torque. Only these
high-load soil tillage segments are published, so that researchers can focus
directly on the most demanding operating condition of the tractor.

The published dataset comprises TEN session files, one per worked field,
totaling approximately 24.7 hours (889,255 samples) of in-field soil tillage
operation.


IMPORTANT: ENGINE TORQUE IS GIVEN AS A PERCENTAGE
--------------------------------------------------------------------------------
The signal ActualEngine_PercTorque (SPN 513) is the actual engine torque
expressed as a PERCENTAGE of the engine reference (maximum) torque. To obtain
the absolute torque in newton-metres, multiply the percentage by the maximum
engine torque of the tractor:

    Torque [Nm] = (ActualEngine_PercTorque / 100) * 450

    Example: 80 % -> 0.80 * 450 = 360 Nm

The maximum engine torque of the Tumosan 81.110 P is 450 Nm.


FILE NAMING CONVENTION
--------------------------------------------------------------------------------
FIELD_{id}_TUMOSAN_81110P_TILLAGE_OP_RAW.tab

  FIELD_{id}        : identifier of the worked field (1-10)
  TUMOSAN_81110P    : tractor model (Tumosan 81.110 P, 105 hp, 450 Nm)
  TILLAGE_OP        : operation type (soil tillage operation)
  RAW               : raw (decoded, unfiltered) CAN bus signal values

FILE LIST  (operation / implement / samples / duration)
--------------------------------------------------------------------------------
  FIELD_1 ...RAW.tab   Ploughing       Unallar plough           48,247   ~1.34 h
  FIELD_2 ...RAW.tab   Ploughing       Unallar plough          140,948   ~3.92 h
  FIELD_3 ...RAW.tab   Ploughing       Unallar plough           54,429   ~1.51 h
  FIELD_4 ...RAW.tab   Ploughing       Unallar plough           70,588   ~1.96 h
  FIELD_5 ...RAW.tab   Ploughing       Unallar plough          132,103   ~3.67 h
  FIELD_6 ...RAW.tab   Ploughing       Unallar plough           56,056   ~1.56 h
  FIELD_7 ...RAW.tab   Rotary tilling  Hisarlar Alabora 300     64,448   ~1.79 h
  FIELD_8 ...RAW.tab   Ploughing       Unallar plough          181,488   ~5.04 h
  FIELD_9 ...RAW.tab   Ploughing       Unallar plough           51,754   ~1.44 h
  FIELD_10 ..RAW.tab   Rotary tilling  Hisarlar Alabora 300     89,194   ~2.48 h

  Total: 889,255 samples, ~24.7 h (ploughing: 8 fields ~20.4 h;
                                   rotary tilling: 2 fields ~4.3 h).

IMPLEMENTS
--------------------------------------------------------------------------------
  Plough        : Unallar reversible plough, 5 furrows (5-bottom),
                  12-inch furrow width (~30 cm worked per bottom),
                  recommended tractor power 90-110 hp. Draft-type, no PTO
                  -> PTO_Status = 0 during ploughing.
  Rotary tiller : Hisarlar Alabora 300, 3 m working width, 60 blades.
                  PTO-driven -> PTO_Status = 1 during rotary tilling.

  The operator-declared implement selection is included in every file as the
  KeypadButon channel (1: plough, 2: rotary tiller). Both the KeypadButon and
  the PTO_Status signals directly distinguish the two operations.


FILE FORMAT
--------------------------------------------------------------------------------
- Tab-separated values (TSV), plain text, UTF-8.
- One header row followed by time-series data.
- Sampling frequency: 10 Hz (uniform 100 ms grid).
- Each file is one continuous soil tillage session on a single worked field.
- Signal values are decoded raw CAN values (no smoothing or interpolation).

COLUMN / SIGNAL DESCRIPTIONS
--------------------------------------------------------------------------------
Signal                    Unit   PGN/SPN  Description
------------------------  -----  -------  -------------------------------------
time_ms                   ms     -        Relative timestamp in milliseconds.
                                          Starts at 0 in every file and
                                          increases in steps of 100 ms (10 Hz).
                                          Absolute recording dates are not
                                          disclosed (anonymization).
ActualEngine_PercTorque   %      513      Actual engine torque as a percentage
                                          of the engine reference (maximum)
                                          torque. Multiply by 450 Nm to obtain
                                          absolute torque (see note above).
EngineSpeed               rpm    190      Actual engine rotational speed.
EngOilTemp1               degC   175      Engine lubrication oil temperature.
EngOilPress               kPa    100      Gauge pressure of the oil in the
                                          engine lubrication system.
EngCoolantTemp            degC   110      Engine coolant temperature.
EngFuelRate               L/h    183      Fuel consumed by the engine per unit
                                          time.
WheelBasedVehicleSpeed    km/h   84       Vehicle speed from wheel speed.
HtcDraftSens1Perc         %      OEM      Draft force at the left lower link of
                                          the rear three-point hitch (% of
                                          sensor range). Rare out-of-range
                                          readings should be treated as
                                          invalid.
HtcDraftSens2Perc         %      OEM      Draft force at the right lower link of
                                          the rear three-point hitch (% of
                                          sensor range). Rare out-of-range
                                          readings should be treated as
                                          invalid.
HtcPositionSensPerc       %      OEM      Rear three-point hitch position (low:
                                          lowered/in work; high: raised/out of
                                          work). Used to separate working
                                          passes from headland turns. Values
                                          slightly outside 0-100 % can occur
                                          (calibration tolerance).
TransferCaseStatus        bit    OEM      Four-wheel-drive transfer case status
                                          (0: disengaged, 1: engaged).
PTO_Status                bit    OEM      Rear power take-off shaft status
                                          (0: disengaged, 1: engaged).
ATSTemp                   degC   OEM      Aftertreatment system (ATS) exhaust
                                          gas temperature.
KeypadButon               -      OEM      Operator-declared implement selection
                                          entered via the in-cab keypad
                                          (1: Unallar reversible plough,
                                           2: Hisarlar Alabora 300 rotary
                                           tiller). Constant within each file.

Engine signals follow the SAE J1939 standard (identified by their Suspect
Parameter Numbers, SPN). Signals marked "OEM" are read from OEM-specific
sensor channels.


IMPORTANT NOTES FOR USERS
--------------------------------------------------------------------------------
1. TORQUE UNIT: ActualEngine_PercTorque is a percentage of reference torque;
   convert to Nm using the 450 Nm maximum (see dedicated note above). Values
   slightly above 100 % can occur because the reference torque is defined per
   the J1939 standard.

2. RAW DATA: Values are decoded raw CAN signals. No smoothing, interpolation,
   or removal of default/initialization values was applied, so users retain
   full control over filtering.

3. SIGNAL DROPOUTS / OUT-OF-RANGE: Individual signals may hold default values
   (e.g., zero in temperature/pressure channels) during dropouts and engine
   start; the draft and hitch-position channels occasionally report values
   outside their nominal ranges. Treat these as invalid and filter as needed.

4. TIME: time_ms starts at 0 in each file on a uniform 100 ms grid. Absolute
   recording dates are intentionally withheld for anonymization.

5. GNSS: GNSS position was used during curation (field/transport separation
   and session assignment) but latitude/longitude coordinates are NOT included
   in the published files for privacy reasons.

6. OPERATING PHASES: Within each session, soil-engagement passes (sustained
   high torque, hitch lowered) alternate with short headland turns (implement
   lifted, torque drop, engine speed rise). Short in-field repositioning
   maneuvers between passes are retained.

7. SOIL CONTEXT: The torque demand of soil tillage depends strongly on soil
   texture. The test fields lie in the Konya Plain, whose agricultural soils
   are predominantly semi-arid, calcareous clay-loam to clay soils; this is
   useful context when interpreting the recorded load levels.


EXAMPLE: READING A FILE IN PYTHON
--------------------------------------------------------------------------------
    import pandas as pd

    df = pd.read_csv("FIELD_1_TUMOSAN_81110P_TILLAGE_OP_RAW.tab", sep="\t")

    # Convert engine torque from percent to Nm
    df["EngineTorque_Nm"] = df["ActualEngine_PercTorque"] / 100.0 * 450.0

    # Relative time in seconds
    df["t_s"] = df["time_ms"] / 1000.0




ACKNOWLEDGEMENTS
--------------------------------------------------------------------------------
The authors thank TUMOSAN Motor ve Traktor A.S. for providing the test
tractor and testing facilities. The authors also thank the farmers and the
field team who supported the instrumentation of the tractor and the
long-term data collection campaign.


LICENSE
--------------------------------------------------------------------------------
This dataset is licensed under a Creative Commons Attribution 4.0
International (CC BY 4.0) license.
================================================================================
