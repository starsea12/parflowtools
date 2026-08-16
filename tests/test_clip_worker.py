import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile


BACKEND_DIR = Path(__file__).resolve().parents[1] / "parflow-website" / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import clip_worker  # noqa: E402


class ClipWorkerTests(unittest.TestCase):
    def test_multiple_basins_are_processed_and_archived(self):
        codes = ["01020000000000", "01020300000000"]

        def fake_run_basin_clip(code, output_dir):
            result_dir = Path(output_dir) / code
            result_dir.mkdir()
            (result_dir / "metadata.json").write_text(code, encoding="utf-8")
            return result_dir

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(
                clip_worker, "run_basin_clip", side_effect=fake_run_basin_clip
            ) as mocked:
                archive_path = Path(clip_worker.run_clip(codes, temp_dir))

            self.assertEqual(mocked.call_count, 2)
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(
                    set(archive.namelist()),
                    {f"{code}/metadata.json" for code in codes},
                )
            job_info = json.loads((archive_path.parent / "job.json").read_text())
            self.assertEqual(job_info["status"], "completed")
            self.assertEqual(job_info["basin_codes"], codes)

    def test_duplicate_ids_are_only_processed_once(self):
        code = "01020000000000"

        def fake_run_basin_clip(basin_code, output_dir):
            result_dir = Path(output_dir) / basin_code
            result_dir.mkdir()
            return result_dir

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(
                clip_worker, "run_basin_clip", side_effect=fake_run_basin_clip
            ) as mocked:
                clip_worker.run_clip([code, code], temp_dir)
            mocked.assert_called_once()


if __name__ == "__main__":
    unittest.main()
