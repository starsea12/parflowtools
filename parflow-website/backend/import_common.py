"""流域数据导入脚本共用的校验、备份和事务逻辑。"""

import re
import shutil
from datetime import datetime
from pathlib import Path

from models import Watershed, db


VALID_LEVELS = {2, 4, 6, 8, 10, 12, 14}


def normalize_basin_id(raw):
    """恢复 Excel/CSV 中可能丢失的前导零，并严格校验 14 位编码。"""
    if raw is None:
        raise ValueError("流域编号为空")
    text = str(raw).strip()
    if not text:
        raise ValueError("流域编号为空")
    if "e" in text.lower() or "." in text:
        try:
            text = str(int(float(text)))
        except ValueError as exc:
            raise ValueError(f"无效流域编号: {raw!r}") from exc
    text = text.zfill(14)
    if not re.fullmatch(r"\d{14}", text):
        raise ValueError(f"流域编号必须是14位数字: {raw!r}")
    return text


def validate_record(record, row_number):
    """校验一个规范字段记录，返回可用于 Watershed 构造的字典。"""
    try:
        basin_id = normalize_basin_id(record.get("id"))
        level = int(float(record.get("level")))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"第 {row_number} 行: {exc}") from exc
    if level not in VALID_LEVELS:
        raise ValueError(f"第 {row_number} 行: 无效级别 {level}")

    region = str(record.get("region") or "").strip()
    if not region:
        raise ValueError(f"第 {row_number} 行: 所属地区为空")

    def optional_float(name):
        value = record.get(name)
        if value is None or str(value).strip() == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"第 {row_number} 行: {name} 不是有效数字") from exc

    return {
        "id": basin_id,
        "name": str(record.get("name") or ""),
        "level": level,
        "region": region,
        "lng": optional_float("lng"),
        "lat": optional_float("lat"),
        "area": optional_float("area"),
        "description": str(record.get("description") or ""),
    }


def replace_watersheds(app, records, make_backup=True):
    """校验完成后，在单个事务中替换全部流域记录。"""
    ids = [record["id"] for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("导入文件包含重复的流域编号")
    if not records:
        raise ValueError("导入文件没有有效记录")

    with app.app_context():
        database_path = Path(db.engine.url.database)
        if make_backup and database_path.exists():
            backup_dir = database_path.parent / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            shutil.copy2(database_path, backup_dir / f"watershed-{stamp}.db")

        try:
            db.session.query(Watershed).delete()
            db.session.bulk_insert_mappings(Watershed, records)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
    return len(records)
