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

### Core Components

| Component | File | Purpose |
|-----------|------|---------|
| **TENT v9 Engine** | `src/tent_v9.py` | Production tensor engine (67K lines) |
| **TENT v10 Vixel** | `src/tent_v10_vixel.py` | Vixel-integrated engine with scroll memory |
| **TENT v10 Pipeline** | `src/tent_v10_pipeline.py` | Streaming pipeline for continuous inference |
| **BRA Bridge** | `src/bra_bridge.py` | Python↔Rust FFI bridge for BRA kernel |
| **BRA Kernel** | `src/bra_kernel.rs` | Rust implementation of core BRA operations |
| **Production Build** | `src/tent_v9_production.py` | Deployment-hardened production variant |

### BRA (Big Reveal Architecture)

The BRA kernel computes **EigenCharge** triplets `(hash, trace, det)` for every data structure:

```
hash  → FNV-1a (u64)     → Identity fingerprinting
trace → Linear F369       → Within-class compactness measurement
det   → Quadratic F369    → Between-class separation measurement
```

This triplet has been formally proven equivalent to the MCR² (Maximal Coding Rate Reduction) objective from representation learning theory, operating entirely in integer space.

### Wallace Transform

The core routing mechanism maps tensor elements through:
1. **F369 Table** — Pre-computed integer lookup (12,000 entries)
2. **Ulam Spiral Addressing** — Storage addresses on a prime-number spiral
3. **Boustrophedon Siphon** — Alternating-direction traversal ensuring every voxel is visited exactly once

---

## Key Properties

- **ADC Resolution**: 10¹⁴ bins (vs float's ~10⁷) — eliminates charge collisions
- **Resonance Scoring**: 3-tier exact match (0/1/2) replaces continuous similarity
- **Deterministic Reproducibility**: Same input → same output, always, on any hardware
- **RC Stack Integration**: Every inference must pass through the constraint gate stack (RC1–RC14)

---

## Directory Structure

```
tent-io/
├── README.md
├── SIP_LICENSE.md
├── build.sh                      # Build script for Rust BRA kernel
├── src/
│   ├── tent_v9.py                # Core TENT engine
│   ├── tent_v9_production.py     # Production variant
│   ├── tent_v10_vixel.py         # Vixel-integrated engine
│   ├── tent_v10_pipeline.py      # Streaming pipeline
│   ├── bra_bridge.py             # Python↔Rust FFI bridge
│   └── bra_kernel.rs             # Rust BRA kernel
├── tests/
│   └── tent_tests.py             # Comprehensive test suite
├── papers/
│   ├── tent_v91_formal.pdf       # Formal specification
│   ├── tent_v91_spec.pdf         # Technical specification
│   ├── trinity_core_BRA.pdf      # BRA architecture paper
│   └── trinity_core_BRA.tex      # LaTeX source
└── docs/
```

---

## Quick Start

```bash
# Build the Rust BRA kernel
chmod +x build.sh && ./build.sh

# Run the test suite
python3 tests/tent_tests.py

# Import the engine
python3 -c "from src.tent_v9 import TENTEngine; print('TENT loaded')"
```

---

## Formal Papers

| Paper | Description |
|-------|-------------|
| `tent_v91_formal.pdf` | Formal mathematical specification of TENT v9.1 |
| `tent_v91_spec.pdf` | Technical implementation specification |
| `trinity_core_BRA.pdf` | Big Reveal Architecture theory and proofs |

---

## License

Copyright (c) 2026, Bradley Wallace (tensorrent). All rights reserved.

This software is governed by the **Sovereign Integrity Protocol (SIP) License v1.1**:
- **Personal/Educational Use**: Perpetual, worldwide, royalty-free.
- **Commercial Use**: Expressly **PROHIBITED** without a prior written license agreement.
- **Unlicensed Commercial Use**: Triggers automatic **8.4% perpetual gross profit penalty**.

See [SIP_LICENSE.md](./SIP_LICENSE.md) for full terms.
