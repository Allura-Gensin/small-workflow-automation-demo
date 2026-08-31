#!/usr/bin/env python3
"""Run a deterministic, file-only inquiry-to-owner-queue demonstration."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable


QUEUE_FIELDS = (
    "submission_id",
    "received_date",
    "contact_ref",
    "topic",
    "preferred_reply_day",
    "queue_owner",
    "status",
)
EXCEPTION_FIELDS = ("submission_id", "reason", "detail")


class WorkflowError(ValueError):
    """Raised when the input or rules cannot be handled safely."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_rules(path: Path) -> dict[str, Any]:
    try:
        rules = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"Rules file is not valid JSON: {path}") from exc

    if not isinstance(rules, dict):
        raise WorkflowError("Rules must be a JSON object.")
    required = rules.get("required_fields")
    allowed = rules.get("allowed_fields")
    if not isinstance(required, list) or not required or not all(isinstance(v, str) for v in required):
        raise WorkflowError("required_fields must be a non-empty list of field names.")
    if not isinstance(allowed, list) or not allowed or not all(isinstance(v, str) for v in allowed):
        raise WorkflowError("allowed_fields must be a non-empty list of field names.")
    if not set(required).issubset(allowed):
        raise WorkflowError("Every required field must also be allowed.")
    if rules.get("queue_owner") != "Example owner":
        raise WorkflowError("This demonstration only permits the made-up queue owner.")
    if rules.get("ready_status") != "OWNER_REVIEW_REQUIRED":
        raise WorkflowError("The ready status must preserve owner review.")
    return rules


def load_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise WorkflowError("Input CSV has no header row.")
            if None in reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
                raise WorkflowError("Input CSV has an invalid or duplicate header.")
            rows = []
            for row in reader:
                if None in row:
                    raise WorkflowError("Input CSV contains more values than its header.")
                rows.append({key: (value or "").strip() for key, value in row.items()})
    except (OSError, UnicodeError, csv.Error) as exc:
        raise WorkflowError(f"Input CSV could not be read: {path}") from exc
    return list(reader.fieldnames), rows


def process_rows(rows: Iterable[dict[str, str]], rules: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    required_fields = tuple(rules["required_fields"])
    allowed_fields = set(rules["allowed_fields"])
    queue: list[dict[str, str]] = []
    exceptions: list[dict[str, str]] = []
    seen: set[str] = set()

    for row_number, source_row in enumerate(rows, start=2):
        row = {key: value for key, value in source_row.items() if key in allowed_fields}
        submission_id = row.get("submission_id", "") or f"ROW-{row_number}"
        missing = [field for field in required_fields if not row.get(field, "")]
        if missing:
            exceptions.append(
                {
                    "submission_id": submission_id,
                    "reason": "missing_required_field",
                    "detail": ",".join(sorted(missing)),
                }
            )
            continue
        if submission_id in seen:
            exceptions.append(
                {
                    "submission_id": submission_id,
                    "reason": "duplicate_submission",
                    "detail": "no_second_queue_item_created",
                }
            )
            continue

        seen.add(submission_id)
        queue.append(
            {
                "submission_id": submission_id,
                "received_date": row["received_date"],
                "contact_ref": row["contact_ref"],
                "topic": row["topic"],
                "preferred_reply_day": row["preferred_reply_day"],
                "queue_owner": rules["queue_owner"],
                "status": rules["ready_status"],
            }
        )

    queue.sort(key=lambda value: value["submission_id"])
    exceptions.sort(key=lambda value: (value["reason"], value["submission_id"]))
    return queue, exceptions


def csv_bytes(fieldnames: tuple[str, ...], rows: list[dict[str, str]]) -> bytes:
    from io import StringIO

    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def run(input_path: Path, rules_path: Path, output_dir: Path) -> dict[str, Any]:
    rules = load_rules(rules_path)
    headers, rows = load_rows(input_path)
    missing_headers = sorted(set(rules["required_fields"]) - set(headers))
    if missing_headers:
        raise WorkflowError(f"Input CSV is missing required columns: {','.join(missing_headers)}")

    queue, exceptions = process_rows(rows, rules)
    queue_data = csv_bytes(QUEUE_FIELDS, queue)
    exceptions_data = csv_bytes(EXCEPTION_FIELDS, exceptions)
    receipt = {
        "counts": {"exceptions": len(exceptions), "ready_for_owner_review": len(queue)},
        "external_calls": 0,
        "files": {
            "exceptions_sha256": sha256_bytes(exceptions_data),
            "input_sha256": sha256_file(input_path),
            "queue_sha256": sha256_bytes(queue_data),
            "rules_sha256": sha256_file(rules_path),
        },
        "live_activation": False,
        "messages_sent": 0,
        "sample_data": "made_up_only",
        "workflow": "inquiry_to_owner_queue",
    }
    receipt_data = json_bytes(receipt)

    atomic_write(output_dir / "team_work_queue.csv", queue_data)
    atomic_write(output_dir / "exceptions.csv", exceptions_data)
    atomic_write(output_dir / "run_receipt.json", receipt_data)
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare an owner-review queue from made-up inquiry rows.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--rules", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        receipt = run(args.input, args.rules, args.output_dir)
    except WorkflowError as exc:
        print(f"Workflow stopped: {exc}")
        return 2
    print(
        "Prepared "
        f"{receipt['counts']['ready_for_owner_review']} owner-review items and "
        f"{receipt['counts']['exceptions']} review notes. No messages were sent."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
