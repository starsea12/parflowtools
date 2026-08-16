#!/usr/bin/env python
"""从 CSV 文件安全导入流域数据。"""

import argparse
import csv

from app import create_app
from import_common import replace_watersheds, validate_record


COLUMN_MAP = {
    "编号": "id",
    "级别": "level",
    "所属地区": "region",
    "经度": "lng",
    "纬度": "lat",
    "面积": "area",
}


def load_csv(file_path):
    with open(file_path, "r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = [name.strip() for name in (reader.fieldnames or [])]
        missing = [column for column in COLUMN_MAP if column not in fieldnames]
        if missing:
            raise ValueError(f"CSV 缺少必要列: {', '.join(missing)}")

        records = []
        for row_number, source_row in enumerate(reader, start=2):
            row = {str(key).strip(): value for key, value in source_row.items()}
            raw = {target: row.get(source) for source, target in COLUMN_MAP.items()}
            records.append(validate_record(raw, row_number))
    return records


def import_csv(file_path, replace=False, make_backup=True):
    if not replace:
        raise ValueError("导入会替换现有数据，请显式传入 --replace")
    records = load_csv(file_path)
    return replace_watersheds(create_app(), records, make_backup=make_backup)


def main(argv=None):
    parser = argparse.ArgumentParser(description="导入 CONCN 流域 CSV 数据")
    parser.add_argument("file", help="CSV 文件路径")
    parser.add_argument("--replace", action="store_true", help="确认替换现有流域数据")
    parser.add_argument("--no-backup", action="store_true", help="不备份当前 SQLite 数据库")
    args = parser.parse_args(argv)
    count = import_csv(args.file, replace=args.replace, make_backup=not args.no_backup)
    print(f"成功导入 {count} 条记录")


if __name__ == "__main__":
    main()
