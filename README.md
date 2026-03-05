# TENT — Tensor Engine for Nondeterministic Transcription

**Bradley Wallace** — Independent Researcher
Licensed under the [Sovereign Integrity Protocol (SIP) v1.1](./SIP_LICENSE.md)

---

## Overview

**TENT** is a deterministic tensor engine that replaces TensorFlow/PyTorch's floating-point pipeline with exact integer arithmetic. Built on the **Big Reveal Architecture (BRA)**, TENT routes tensors through a 32³ voxel lattice using gravitational field equations, boustrophedon siphon traversal, and the Wallace Transform.

TENT eliminates:
- **Floating-point drift** → all operations are exact integer
- **Stochastic gradient descent** → replaced by deterministic constraint satisfaction (RC Stack)
- **Black-box inference** → every decision has a traceable integer charge path

---

## Architecture

### Core Engine

| File | Size | Purpose |
|------|------|---------|
| `src/tent_v9.py` | 68K | Core TENT v9 engine — production tensor routing |
| `src/tent_v9_production.py` | 70K | Deployment-hardened production variant |
| `src/tent_v10_vixel.py` | 28K | Vixel-integrated engine with scroll memory |
| `src/tent_v10_pipeline.py` | 18K | Streaming pipeline for continuous inference |
| `src/bra_bridge.py` | 5K | Python↔Rust FFI bridge |
| `src/bra_kernel.rs` | 4K | Rust BRA kernel (compiled to cdylib) |

### BRA (Big Reveal Architecture)

EigenCharge triplets `(hash, trace, det)` for every data structure:

```
hash  → FNV-1a (u64)      → Identity fingerprinting
trace → Linear F369        → Within-class compactness
det   → Quadratic F369     → Between-class separation
```

Formally equivalent to MCR² (Maximal Coding Rate Reduction) from representation learning, operating entirely in integer space.

### Wallace Transform

1. **F369 Table** — Pre-computed integer lookup (12,000 entries)
2. **Ulam Spiral Addressing** — Storage addresses on prime-number spiral
3. **Boustrophedon Siphon** — Alternating-direction traversal (every voxel visited exactly once)

---

## Key Properties

- **ADC Resolution**: 10¹⁴ bins (vs float's ~10⁷) — eliminates charge collisions
- **Resonance Scoring**: 3-tier exact match (0/1/2) replaces continuous similarity
- **Deterministic Reproducibility**: Same input → same output, always, on any hardware
- **RC Stack Integration**: Every inference passes through constraint gates RC1–RC14

---

## Directory Structure

```
tent-io/
├── src/
│   ├── tent_v9.py                # Core engine (68K)
│   ├── tent_v9_production.py     # Production variant (70K)
│   ├── tent_v10_vixel.py         # Vixel integration (28K)
│   ├── tent_v10_pipeline.py      # Streaming pipeline (18K)
│   ├── bra_bridge.py             # Python↔Rust FFI (5K)
│   └── bra_kernel.rs             # Rust BRA kernel (4K)
├── tests/
│   └── tent_tests.py             # Test suite
├── papers/
│   ├── tent_v91_formal.pdf       # Formal specification
│   ├── tent_v91_spec.pdf         # Technical specification
│   ├── trinity_core_BRA.pdf      # BRA architecture paper
│   └── trinity_core_BRA.tex      # LaTeX source
├── build.sh                      # Rust kernel build script
└── SIP_LICENSE.md
```

---

## Quick Start

```bash
chmod +x build.sh && ./build.sh
python3 tests/tent_tests.py
python3 -c "from src.tent_v9 import TENTEngine; print('TENT loaded')"
```

---

## Related Repositories

- [Theory Paper](https://github.com/tensorrent/Unified-Stability-Epistemic-Limits-Nonlinear-mode-collaps-in-Coupled-Systems) — Unified Stability framework
- [Sovereign Stack](https://github.com/tensorrent/Sovereign-Stack-Complete) — Full suite (includes TENT)
- [RC Stack](https://github.com/tensorrent/RC1-Deterministic-Constraint-Projection-Layer) — Constraint gate architecture

---

## License

Copyright (c) 2026, Bradley Wallace (tensorrent). All rights reserved.

**SIP License v1.1** — Personal/educational: royalty-free. Commercial: **prohibited** without prior license. Unlicensed commercial use triggers **8.4% perpetual gross profit penalty**.

See [SIP_LICENSE.md](./SIP_LICENSE.md) for full terms.
