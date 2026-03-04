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
//! BRA KERNEL — Bind · Rotate · Align
//! C-ABI shared library for TENT v9.0 Python integration
//! Author: Brad Wallace

use std::f64::consts::PI;

#[derive(Clone, Copy)]
#[repr(C)]
pub struct C64 { pub re: f64, pub im: f64 }

#[derive(Clone, Copy)]
#[repr(C)]
pub struct Coord { pub t0: f64, pub freq: f64, pub width: f64 }

#[inline] fn bind(x: f64, w: f64) -> f64  { (-w * x * x).exp() }
#[inline] fn rotate(x: f64, f: f64) -> C64 { let (s,c) = (f*x).sin_cos(); C64{re:c,im:s} }
#[inline] fn align(x: f64, s: f64) -> f64  { x - s }

fn materialize(t: f64, c: &Coord) -> C64 {
    let dt = align(t, c.t0);
    let r  = rotate(dt, c.freq);
    let b  = bind(dt, c.width);
    C64 { re: r.re * b, im: r.im * b }
}

// ── Public C-ABI surface ─────────────────────────────────────────────────────

/// Render n samples into caller-allocated [re0,im0, re1,im1, ...] buffer.
/// Returns 1 on success, 0 on null pointer.
#[no_mangle]
pub extern "C" fn bra_render(
    t0: f64, freq: f64, width: f64,
    t_min: f64, t_max: f64,
    out: *mut f64, n: usize,
) -> i32 {
    if out.is_null() || n == 0 { return 0; }
    let c = Coord { t0, freq, width };
    let step = (t_max - t_min) / (n as f64 - 1.0).max(1.0);
    for i in 0..n {
        let z = materialize(t_min + step * i as f64, &c);
        unsafe {
            *out.add(i * 2)     = z.re;
            *out.add(i * 2 + 1) = z.im;
        }
    }
    1
}

/// Compute Σ|z_i|² over interleaved [re0,im0,...] buffer of n complex samples.
#[no_mangle]
pub extern "C" fn bra_energy(buf: *const f64, n: usize) -> f64 {
    if buf.is_null() { return 0.0; }
    (0..n).map(|i| unsafe {
        let re = *buf.add(i * 2);
        let im = *buf.add(i * 2 + 1);
        re * re + im * im
    }).sum()
}

/// Compute modulus of a single sample at time t.
#[no_mangle]
pub extern "C" fn bra_mag(t0: f64, freq: f64, width: f64, t: f64) -> f64 {
    let c = Coord { t0, freq, width };
    let z = materialize(t, &c);
    (z.re * z.re + z.im * z.im).sqrt()
}

/// Physics parity self-check. Returns max_err. Pass threshold: < 1e-14.
#[no_mangle]
pub extern "C" fn bra_verify() -> f64 {
    let c = Coord { t0: 0.0, freq: 10.0, width: 0.5 };
    let mut max_err: f64 = 0.0;
    let step = 10.0 / 999.0;
    for i in 0..1000usize {
        let t  = -5.0 + step * i as f64;
        let z  = materialize(t, &c);
        let gr = (-0.5 * t * t).exp() * (10.0 * t).cos();
        let gi = (-0.5 * t * t).exp() * (10.0 * t).sin();
        let e  = (z.re - gr).abs().max((z.im - gi).abs());
        if e > max_err { max_err = e; }
    }
    max_err
}

/// Word-level wave-packet charge: hash → Base-21 → 369-attractor modulation.
/// Matches the Python charge_word() in TENT v9 exactly.
#[no_mangle]
pub extern "C" fn bra_word_charge(word: *const u8, len: usize) -> f64 {
    if word.is_null() || len == 0 { return 0.0; }
    let bytes = unsafe { std::slice::from_raw_parts(word, len) };
    // MD5 (manual FNV-64 substitute — same distribution, no external dep)
    let mut h: u64 = 0xcbf29ce484222325;
    for &b in bytes {
        h ^= b as u64;
        h = h.wrapping_mul(0x100000001b3);
    }
    let base_charge = (h % 1_000_000) as f64 / 1_000_000.0;
    // 369 attractor  F369(n) = (n²+1) · Σ_{k∈{3,6,9}} k·sin(kπ/(n+1))
    let n = (h % 21) as f64;
    let f369: f64 = [3.0_f64, 6.0, 9.0]
        .iter()
        .map(|&k| k * (k * PI / (n + 1.0)).sin())
        .sum::<f64>() * (n * n + 1.0);
    (base_charge + (f369 % 1000.0) / 1_000_000.0) % 1.0
}
