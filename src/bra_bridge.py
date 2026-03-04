# -----------------------------------------------------------------------------
# SOVEREIGN INTEGRITY PROTOCOL (SIP) LICENSE v1.1
# 
# Copyright (c) 2026, Bradley Wallace (tensorrent). All rights reserved.
# 
# This software, research, and associated mathematical implementations are
# strictly governed by the Sovereign Integrity Protocol (SIP) License v1.1:
# - Personal/Educational Use: Perpetual, worldwide, royalty-free.
# - Commercial Use: Expressly PROHIBITED without a prior written license.
# - Unlicensed Commercial Use: Triggers automatic 8.4% perpetual gross
#   profit penalty (distrust fee + reparation fee).
# 
# See the SIP_LICENSE.md file in the repository root for full terms.
# -----------------------------------------------------------------------------
"""
bra_bridge.py — Python ctypes binding for the BRA Rust kernel (libbra.so)

Exposes:
    bra_render(t0, freq, width, t_min, t_max, n)  -> list[complex]
    bra_energy(samples)                           -> float
    bra_mag(t0, freq, width, t)                   -> float
    bra_verify()                                  -> float   (max_err; PASS < 1e-14)
    bra_word_charge(word: str)                    -> float   [0, 1)
"""

import ctypes
import os
import array
from pathlib import Path

# ── Locate shared library ─────────────────────────────────────────────────────
import sys
_HERE   = Path(__file__).parent
_BINDIR = _HERE.parent / "bin"

# macOS → .dylib, Linux → .so
if sys.platform == "darwin":
    _SO = _BINDIR / "libbra.dylib"
else:
    _SO = _BINDIR / "libbra.so"

if not _SO.exists():
    raise FileNotFoundError(
        f"libbra not found at {_SO}. "
        "Run build.sh to compile the BRA kernel first."
    )

_lib = ctypes.CDLL(str(_SO))

# ── Function signatures ───────────────────────────────────────────────────────
_lib.bra_render.restype  = ctypes.c_int
_lib.bra_render.argtypes = [
    ctypes.c_double,   # t0
    ctypes.c_double,   # freq
    ctypes.c_double,   # width
    ctypes.c_double,   # t_min
    ctypes.c_double,   # t_max
    ctypes.POINTER(ctypes.c_double),  # out (interleaved re/im)
    ctypes.c_size_t,   # n (complex samples)
]

_lib.bra_energy.restype  = ctypes.c_double
_lib.bra_energy.argtypes = [
    ctypes.POINTER(ctypes.c_double),  # buf (interleaved re/im)
    ctypes.c_size_t,   # n
]

_lib.bra_mag.restype  = ctypes.c_double
_lib.bra_mag.argtypes = [
    ctypes.c_double, ctypes.c_double, ctypes.c_double,  # t0, freq, width
    ctypes.c_double,  # t
]

_lib.bra_verify.restype  = ctypes.c_double
_lib.bra_verify.argtypes = []

_lib.bra_word_charge.restype  = ctypes.c_double
_lib.bra_word_charge.argtypes = [
    ctypes.POINTER(ctypes.c_uint8),  # word bytes
    ctypes.c_size_t,                 # len
]

# ── Public Python API ─────────────────────────────────────────────────────────

def bra_render(t0: float, freq: float, width: float,
               t_min: float, t_max: float, n: int) -> list:
    """
    Render n complex samples of the wave packet f(t) = exp(-w*(t-t0)^2)*exp(i*freq*(t-t0)).
    Returns list of complex values.
    """
    buf = (ctypes.c_double * (n * 2))()
    ok  = _lib.bra_render(t0, freq, width, t_min, t_max, buf, n)
    if not ok:
        raise RuntimeError("bra_render returned failure")
    return [complex(buf[i*2], buf[i*2+1]) for i in range(n)]


def bra_energy(samples: list) -> float:
    """Compute Σ|z|² for a list of complex samples (no dt factor)."""
    n   = len(samples)
    buf = (ctypes.c_double * (n * 2))()
    for i, z in enumerate(samples):
        buf[i*2]   = z.real
        buf[i*2+1] = z.imag
    return _lib.bra_energy(buf, n)


def bra_mag(t0: float, freq: float, width: float, t: float) -> float:
    """Return |f(t)| for a single sample."""
    return _lib.bra_mag(t0, freq, width, t)


def bra_verify() -> float:
    """
    Run BRA internal physics parity check.
    Returns max pointwise error vs analytical ground truth.
    Pass threshold: < 1e-14.
    """
    return _lib.bra_verify()


def bra_word_charge(word: str) -> float:
    """
    Compute the wave-packet charge for a word token.
    Uses FNV-64 hash + Base-21 + 369-attractor modulation.
    Returns value in [0, 1).
    """
    b = word.lower().encode()
    arr = (ctypes.c_uint8 * len(b))(*b)
    return _lib.bra_word_charge(arr, len(b))


# ── Quick self-test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    err = bra_verify()
    status = "PASS" if err < 1e-14 else "FAIL"
    print(f"BRA bridge loaded — physics parity: {status}  max_err={err:.2e}")
    samples = bra_render(0.0, 10.0, 0.5, -5.0, 5.0, 1000)
    e = bra_energy(samples)
    print(f"  energy(1000 samples) = {e:.6f}")
    print(f"  bra_mag(t0=0, f=10, w=0.5, t=0) = {bra_mag(0.0, 10.0, 0.5, 0.0):.6f}")
    print(f"  charge('heisenberg') = {bra_word_charge('heisenberg'):.6f}")
