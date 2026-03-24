#!/usr/bin/env python3
"""Prepare local MMLU/GSM8K corpora for LLT training.

Outputs JSONL files with stable schema so training scripts do not need to know
about source-specific layouts.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

# harness/training -> harness/fixtures/training (repo-relative default for --out-dir)
_DEFAULT_OUT_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "training"


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")


def parse_mmlu_subject_from_filename(filename: str) -> str:
    # Example: high_school_physics_test.csv -> high_school_physics
    if filename.endswith("_test.csv"):
        return filename[: -len("_test.csv")]
    if filename.endswith("_dev.csv"):
        return filename[: -len("_dev.csv")]
    if filename.endswith("_val.csv"):
        return filename[: -len("_val.csv")]
    return filename.replace(".csv", "")


def load_mmlu(mmlu_dir: Path) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {"dev": [], "test": [], "train": []}
    for split in ("dev", "test", "val"):
        split_dir = mmlu_dir / split
        if not split_dir.exists():
            continue
        target_split = "train" if split == "val" else split
        for csv_path in sorted(split_dir.glob("*.csv")):
            subject = parse_mmlu_subject_from_filename(csv_path.name)
            with csv_path.open("r", encoding="utf-8") as f:
                reader = csv.reader(f)
                for i, row in enumerate(reader):
                    if len(row) != 6:
                        continue
                    out[target_split].append(
                        {
                            "id": f"mmlu::{subject}::{split}::{i}",
                            "task": "mmlu",
                            "source": "helm_mmlu_csv",
                            "split": target_split,
                            "subject": subject,
                            "question": row[0],
                            "choices": {"A": row[1], "B": row[2], "C": row[3], "D": row[4]},
                            "target": row[5].strip().upper(),
                        }
                    )
    return out


def extract_gsm8k_final_answer(answer: str) -> str:
    marker = "####"
    if marker in answer:
        return answer.split(marker, 1)[1].strip().replace(",", "")
    return answer.strip().replace(",", "")


def load_gsm8k_from_jsonl_dir(gsm8k_dir: Path) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {"train": [], "test": []}
    for split in ("train", "test"):
        p = gsm8k_dir / f"{split}.jsonl"
        if not p.exists():
            continue
        with p.open("r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                item = json.loads(line)
                out[split].append(
                    {
                        "id": f"gsm8k::{split}::{i}",
                        "task": "gsm8k",
                        "source": "jsonl_local",
                        "split": split,
                        "question": item.get("question", ""),
                        "answer_full": item.get("answer", ""),
                        "target": extract_gsm8k_final_answer(item.get("answer", "")),
                    }
                )
    return out


def load_gsm8k_from_hf() -> dict[str, list[dict[str, Any]]]:
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise RuntimeError(
            "datasets package is required for --download-gsm8k. "
            "Install with: python3 -m pip install datasets"
        ) from exc

    ds = load_dataset("openai/gsm8k", "main")
    out: dict[str, list[dict[str, Any]]] = {"train": [], "test": []}
    for split in ("train", "test"):
        for i, item in enumerate(ds[split]):
            out[split].append(
                {
                    "id": f"gsm8k::{split}::{i}",
                    "task": "gsm8k",
                    "source": "hf_openai_gsm8k_main",
                    "split": split,
                    "question": item.get("question", ""),
                    "answer_full": item.get("answer", ""),
                    "target": extract_gsm8k_final_answer(item.get("answer", "")),
                }
            )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare MMLU/GSM8K corpora for LLT training")
    parser.add_argument(
        "--mmlu-dir",
        type=Path,
        default=Path("/Users/coo-koba42/dev/gold_benchmarks/helm/output/scenarios/mmlu/data"),
        help="Directory with MMLU split folders (dev/test/val).",
    )
    parser.add_argument(
        "--gsm8k-dir",
        type=Path,
        default=None,
        help="Directory containing train.jsonl and test.jsonl for GSM8K.",
    )
    parser.add_argument(
        "--download-gsm8k",
        action="store_true",
        help="Download GSM8K from Hugging Face via datasets library.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=_DEFAULT_OUT_DIR,
        help="Output directory for normalized JSONL corpora (default: harness/fixtures/training next to this script).",
    )
    args = parser.parse_args()

    mmlu = load_mmlu(args.mmlu_dir)
    write_jsonl(args.out_dir / "mmlu_train.jsonl", mmlu["train"] + mmlu["dev"])
    write_jsonl(args.out_dir / "mmlu_test.jsonl", mmlu["test"])

    gsm8k: dict[str, list[dict[str, Any]]] = {"train": [], "test": []}
    if args.gsm8k_dir:
        gsm8k = load_gsm8k_from_jsonl_dir(args.gsm8k_dir)
    elif args.download_gsm8k:
        gsm8k = load_gsm8k_from_hf()

    if gsm8k["train"] or gsm8k["test"]:
        write_jsonl(args.out_dir / "gsm8k_train.jsonl", gsm8k["train"])
        write_jsonl(args.out_dir / "gsm8k_test.jsonl", gsm8k["test"])

    print(
        json.dumps(
            {
                "mmlu_train_rows": len(mmlu["train"] + mmlu["dev"]),
                "mmlu_test_rows": len(mmlu["test"]),
                "gsm8k_train_rows": len(gsm8k["train"]),
                "gsm8k_test_rows": len(gsm8k["test"]),
                "out_dir": str(args.out_dir),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
