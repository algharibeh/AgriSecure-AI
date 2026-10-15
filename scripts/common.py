"""AgriSecure-AI Phase 1 - shared definitions.

Part of the AgriSecure-AI project.

This module encodes the J1939-71 mapping used to reconstruct a CAN / SAE J1939
frame stream from the published Tumosan decoded-signal recordings. The source
dataset (Mendeley DOI 10.17632/bbjtjrsxvx.2, CC BY 4.0) contains decoded signal
time series at 10 Hz, not raw frames. Here each recorded signal is placed back
into the standard J1939 parameter group that carries it, at that group's
standard transmission rate, with the real recorded value packed using the
documented SPN resolution/offset. The frame layer is therefore a faithful
RECONSTRUCTION; the signal content is REAL tractor data.

Nothing here attacks any system. Anomaly injection (a separate script) operates
only on this simulated frame stream.
"""
from __future__ import annotations
import csv
import struct
from dataclasses import dataclass, field
from pathlib import Path

NA = 0xFF  # J1939 "parameter not available" byte fill


@dataclass(frozen=True)
class SPNField:
    """One signal packed into a PGN payload."""
    name: str          # column name in the Tumosan .tab files (or None if derived)
    spn: int
    start_byte: int    # 0-indexed first byte in the 8-byte payload
    length: int        # bytes
    resolution: float  # physical units per bit
    offset: float      # physical = raw * resolution + offset
    unit: str


@dataclass(frozen=True)
class PGNSpec:
    pgn: int
    label: str
    priority: int
    source_addr: int       # transmitting ECU address
    rate_ms: int           # standard broadcast period
    fields: tuple          # tuple[SPNField, ...]

    @property
    def can_id(self) -> int:
        # 29-bit: prio(3) | reserved/DP(1+1 via PGN) | PF | PS | SA
        # For PDU2 (PF >= 240) PS is group extension; PGN already encodes PF/PS.
        pf = (self.pgn >> 8) & 0xFF
        ps = self.pgn & 0xFF
        return (self.priority << 26) | (pf << 16) | (ps << 8) | self.source_addr


# Source addresses (standard J1939 preferred addresses)
SA_ENGINE = 0x00        # engine #1
SA_TRANS = 0x03         # transmission / transfer case
SA_IMPLEMENT = 0x81     # rear hitch / implement management (ISO 11783 range)
SA_BODY = 0x21          # body controller (keypad / aux)

# --- J1939-71 parameter groups carrying the recorded signals ---
PGN_SPECS = [
    PGNSpec(
        pgn=61444, label="EEC1", priority=3, source_addr=SA_ENGINE, rate_ms=100,
        fields=(
            SPNField("ActualEngine_PercTorque", 513, 2, 1, 1.0, -125.0, "%"),
            SPNField("EngineSpeed", 190, 3, 2, 0.125, 0.0, "rpm"),
        ),
    ),
    PGNSpec(
        pgn=65266, label="LFE1", priority=6, source_addr=SA_ENGINE, rate_ms=100,
        fields=(
            SPNField("EngFuelRate", 183, 0, 2, 0.05, 0.0, "L/h"),
        ),
    ),
    PGNSpec(
        pgn=65265, label="CCVS1", priority=6, source_addr=SA_ENGINE, rate_ms=100,
        fields=(
            SPNField("WheelBasedVehicleSpeed", 84, 1, 2, 1.0 / 256.0, 0.0, "km/h"),
        ),
    ),
    PGNSpec(
        pgn=65262, label="ET1", priority=6, source_addr=SA_ENGINE, rate_ms=1000,
        fields=(
            SPNField("EngCoolantTemp", 110, 0, 1, 1.0, -40.0, "degC"),
            SPNField("EngOilTemp1", 175, 2, 2, 0.03125, -273.0, "degC"),
        ),
    ),
    PGNSpec(
        pgn=65263, label="EFL/P1", priority=6, source_addr=SA_ENGINE, rate_ms=500,
        fields=(
            SPNField("EngOilPress", 100, 3, 1, 4.0, 0.0, "kPa"),
        ),
    ),
    PGNSpec(
        pgn=65091, label="PTO", priority=6, source_addr=SA_IMPLEMENT, rate_ms=100,
        fields=(
            # PTO engaged/status packed as a 2-bit state in byte 0; stored 0/1 here.
            SPNField("PTO_Status", 976, 0, 1, 1.0, 0.0, "state"),
        ),
    ),
    # Rear hitch position. Standard SPN 1873 is 0.4 %/bit over 0..100 %; the
    # recorded sensor reports out-of-nominal excursions (-10..117 %), so a wider
    # 2-byte 0.1 %/bit, -200 offset field is used to carry the real value
    # losslessly. This is a documented reconstruction choice (see datasheet).
    PGNSpec(
        pgn=65093, label="RearHitch", priority=6, source_addr=SA_IMPLEMENT, rate_ms=100,
        fields=(
            SPNField("HtcPositionSensPerc", 1873, 0, 2, 0.1, -200.0, "%"),
        ),
    ),
    # Manufacturer-proprietary B group for tractor-specific signals that have no
    # standard broadcast PGN (draft sensors, transfer case, keypad). Draft
    # sensors span -126..128 %, hence signed 2-byte 0.1 %/bit, -200 offset.
    PGNSpec(
        pgn=65280, label="PROP_B_AUX", priority=6, source_addr=SA_BODY, rate_ms=200,
        fields=(
            SPNField("HtcDraftSens1Perc", -1, 0, 2, 0.1, -200.0, "%"),
            SPNField("HtcDraftSens2Perc", -2, 2, 2, 0.1, -200.0, "%"),
            SPNField("TransferCaseStatus", -3, 4, 1, 1.0, 0.0, "state"),
            SPNField("KeypadButon", -4, 5, 1, 1.0, 0.0, "state"),
        ),
    ),
]

PGN_BY_LABEL = {s.label: s for s in PGN_SPECS}

# Physical plausibility limits for the rule-based detector (engineering bounds,
# not dataset-fit values). Used only on normal signals; documented in report.
SIGNAL_LIMITS = {
    "EngineSpeed": (0.0, 3000.0, 600.0),          # min, max, max |delta| per 100ms
    "ActualEngine_PercTorque": (-10.0, 125.0, 60.0),
    "EngFuelRate": (0.0, 120.0, 40.0),
    "WheelBasedVehicleSpeed": (0.0, 60.0, 8.0),
    "EngCoolantTemp": (-40.0, 130.0, 10.0),
    "EngOilTemp1": (-40.0, 160.0, 10.0),
    "EngOilPress": (0.0, 1000.0, 200.0),
    "HtcPositionSensPerc": (0.0, 100.0, 50.0),
}

# frame schema (one row per CAN frame; candump-style: metadata + raw payload).
# Decoded physical values are recovered from data_hex via decode_field(), so the
# dataset is self-describing and the packing is verifiable by any consumer.
FRAME_COLUMNS = [
    "t_s", "can_id_hex", "pgn", "label", "priority", "source_addr",
    "dlc", "data_hex", "attack", "attack_type",
]


def pack_value(raw_phys, fld: SPNField) -> list:
    """Return the little-endian bytes for one SPN field, or NA fill if missing."""
    out = [NA] * fld.length
    if raw_phys is None:
        return out
    raw = int(round((raw_phys - fld.offset) / fld.resolution))
    maxraw = (1 << (8 * fld.length)) - 1
    if raw < 0:
        raw = 0
    if raw > maxraw:
        raw = maxraw
    for i in range(fld.length):
        out[i] = (raw >> (8 * i)) & 0xFF
    return out


def pack_frame(spec: PGNSpec, row: dict) -> bytearray:
    """Build the 8-byte J1939 payload for one PGN from a signal row."""
    data = bytearray([NA] * 8)
    for fld in spec.fields:
        if fld.name in row and row[fld.name] is not None:
            raw_bytes = pack_value(row[fld.name], fld)
            for i, b in enumerate(raw_bytes):
                data[fld.start_byte + i] = b
    return data


def decode_field(data: bytearray, fld: SPNField):
    """Inverse of pack_value; returns physical value or None if NA."""
    raw = 0
    for i in range(fld.length):
        b = data[fld.start_byte + i]
        raw |= b << (8 * i)
    if all(data[fld.start_byte + i] == NA for i in range(fld.length)):
        return None
    return raw * fld.resolution + fld.offset


def _denul(fh):
    """Strip stray NUL bytes that appear in a few source rows."""
    for line in fh:
        yield line.replace("\x00", "")


def load_tab(path, keep_cols=None):
    """Yield dict rows from a Tumosan .tab file. Values parsed to float or None."""
    with open(path, "r", newline="", encoding="utf-8", errors="replace") as fh:
        rdr = csv.DictReader(_denul(fh), delimiter="\t")
        for row in rdr:
            out = {}
            for k, v in row.items():
                if v is None or v == "" or v == "NaN":
                    out[k] = None
                else:
                    try:
                        out[k] = float(v)
                    except ValueError:
                        out[k] = None
            yield out


RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "tumosan_raw"
DATASET_DIR = Path(__file__).resolve().parent.parent / "dataset"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
