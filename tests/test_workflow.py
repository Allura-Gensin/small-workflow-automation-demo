from __future__ import annotations

import json
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import run_workflow  # noqa: E402


INPUT = ROOT / "fixtures/made_up_inquiries.csv"
RULES = ROOT / "workflow_rules.json"
EXPECTED = ROOT / "expected"


class WorkflowTests(unittest.TestCase):
    def run_to(self, output_dir: Path) -> dict:
        return run_workflow.run(INPUT, RULES, output_dir)

    def test_generated_files_match_golden_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            self.run_to(output)
            for name in ("team_work_queue.csv", "exceptions.csv", "run_receipt.json"):
                self.assertEqual((output / name).read_bytes(), (EXPECTED / name).read_bytes())

    def test_only_two_valid_items_reach_owner_queue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            receipt = self.run_to(output)
            lines = (output / "team_work_queue.csv").read_text(encoding="utf-8").splitlines()
            self.assertEqual(receipt["counts"]["ready_for_owner_review"], 2)
            self.assertEqual(len(lines), 3)
            self.assertIn("EXAMPLE-001", lines[1])
            self.assertIn("EXAMPLE-002", lines[2])

    def test_duplicate_and_missing_rows_create_review_notes_not_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            self.run_to(output)
            exceptions = (output / "exceptions.csv").read_text(encoding="utf-8")
            queue = (output / "team_work_queue.csv").read_text(encoding="utf-8")
            self.assertIn("duplicate_submission", exceptions)
            self.assertIn("missing_required_field", exceptions)
            self.assertNotIn("EXAMPLE-003", queue)
            self.assertEqual(queue.count("EXAMPLE-001"), 1)

    def test_unexpected_input_column_never_reaches_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            self.run_to(output)
            combined = b"".join(path.read_bytes() for path in output.iterdir())
            self.assertNotIn(b"unexpected_notes", combined)
            self.assertNotIn(b"DO-NOT-COPY", combined)

    def test_second_run_is_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_dir, second_dir = Path(first), Path(second)
            self.run_to(first_dir)
            self.run_to(second_dir)
            for name in ("team_work_queue.csv", "exceptions.csv", "run_receipt.json"):
                self.assertEqual((first_dir / name).read_bytes(), (second_dir / name).read_bytes())

    def test_malformed_rules_exit_nonzero_without_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            bad_rules = base / "bad.json"
            bad_rules.write_text("{not-json", encoding="utf-8")
            output = base / "output"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "run_workflow.py"),
                    "--input",
                    str(INPUT),
                    "--rules",
                    str(bad_rules),
                    "--output-dir",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())

    def test_malformed_csv_exits_nonzero_without_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            bad_input = base / "bad.csv"
            bad_input.write_text("submission_id,topic\nEXAMPLE-1,hello,extra\n", encoding="utf-8")
            output = base / "output"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "run_workflow.py"),
                    "--input",
                    str(bad_input),
                    "--rules",
                    str(RULES),
                    "--output-dir",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())

    def test_network_is_never_used(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.object(socket, "socket", side_effect=AssertionError("network attempted")):
                receipt = self.run_to(Path(temp_dir))
            self.assertEqual(receipt["external_calls"], 0)
            self.assertEqual(receipt["messages_sent"], 0)
            self.assertFalse(receipt["live_activation"])

    def test_outputs_contain_no_contact_or_credential_patterns(self) -> None:
        blocked = (b"@", b"http://", b"https://", b"password", b"secret", b"api_key", b"555-")
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            self.run_to(output)
            combined = b"\n".join(path.read_bytes().lower() for path in sorted(output.iterdir()))
            for pattern in blocked:
                self.assertNotIn(pattern, combined)

    def test_receipt_has_expected_controls_and_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            receipt = self.run_to(output)
            self.assertEqual(receipt["sample_data"], "made_up_only")
            self.assertEqual(receipt["counts"], {"exceptions": 2, "ready_for_owner_review": 2})
            self.assertEqual(len(receipt["files"]), 4)
            json.loads((output / "run_receipt.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
