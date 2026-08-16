"""执行裁剪任务并将一个或多个流域结果打包。"""

import json
import sys
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from concnshare.run_two import run_basin_clip, validate_basin_code  # noqa: E402


def run_clip(watershed_ids, job_root):
    """顺序裁剪所有流域，在独立任务目录内生成 ZIP 并返回其路径。"""
    if not watershed_ids:
        raise ValueError("流域编号列表为空")

    basin_codes = []
    seen = set()
    for watershed_id in watershed_ids:
        code = validate_basin_code(watershed_id)
        if code not in seen:
            basin_codes.append(code)
            seen.add(code)

    job_id = uuid.uuid4().hex
    job_dir = Path(job_root) / job_id
    output_dir = job_dir / "outputs"
    output_dir.mkdir(parents=True)

    job_info = {
        "job_id": job_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "basin_codes": basin_codes,
        "status": "running",
    }
    job_file = job_dir / "job.json"
    job_file.write_text(json.dumps(job_info, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        result_dirs = [run_basin_clip(code, output_dir) for code in basin_codes]
        zip_path = job_dir / f"clip_result_{job_id}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for result_dir in result_dirs:
                for file_path in result_dir.rglob("*"):
                    if file_path.is_file():
                        archive.write(file_path, file_path.relative_to(output_dir))
        job_info["status"] = "completed"
        job_info["archive"] = zip_path.name
        return str(zip_path)
    except Exception as exc:
        job_info["status"] = "failed"
        job_info["error"] = str(exc)
        raise
    finally:
        job_file.write_text(
            json.dumps(job_info, ensure_ascii=False, indent=2), encoding="utf-8"
        )
