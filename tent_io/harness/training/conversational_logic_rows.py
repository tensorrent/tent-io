#!/usr/bin/env python3
"""Deterministic synthetic conversational-logic rows for LLT training/eval."""

from __future__ import annotations

from typing import Any

LABELS = ["A", "B", "C", "D"]


def _sample_numbers(rng_state: int) -> tuple[int, int]:
    # Deterministic pseudo-random pair from integer state.
    a = 2 + ((rng_state * 7 + 11) % 17)
    b = 2 + ((rng_state * 13 + 5) % 11)
    return a, b


def build_conversational_logic_rows(count: int, seed: int, split: str) -> list[dict[str, Any]]:
    """Generate deterministic conversation-style logic rows.

    Label mapping:
    - A: add
    - B: subtract
    - C: multiply
    - D: divide
    """
    if count <= 0:
        return []

    split_offset = 0 if split == "train" else 10_000
    rows: list[dict[str, Any]] = []
    for i in range(count):
        state = seed + split_offset + i
        op_idx = (state * 31 + 17) % 4
        a, b = _sample_numbers(state)
        if op_idx == 3:
            # Keep divide prompts integer-friendly for stable logic phrasing.
            a = a * b

        op_token = ["add", "subtract", "multiply", "divide"][op_idx]
        signal = f"logic_signal_{op_token}"
        question = (
            f"User: In this conversation, solve the logic step with {signal}. "
            f"Numbers are {a} and {b}. "
            "Assistant: choose the correct reasoning channel for the requested operation."
        )
        choices = [
            "use channel add reasoning",
            "use channel subtract reasoning",
            "use channel multiply reasoning",
            "use channel divide reasoning",
        ]
        rows.append(
            {
                "question": question,
                "choices": choices,
                "target": LABELS[op_idx],
                "source": "conversational_logic",
            }
        )
    return rows
