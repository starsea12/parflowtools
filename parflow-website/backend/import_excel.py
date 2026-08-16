#!/usr/bin/env python
"""从 Excel 文件安全导入流域数据。"""

import argparse

import pandas as pd

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


def load_excel(file_path):
    dataframe = pd.read_excel(file_path, dtype={"编号": str}, engine="openpyxl")
    missing = [column for column in COLUMN_MAP if column not in dataframe.columns]
    if missing:
        raise ValueError(f"Excel 缺少必要列: {', '.join(missing)}")

    records = []
    for index, row in dataframe.iterrows():
        raw = {target: row[source] for source, target in COLUMN_MAP.items()}
        raw = {
            key: None if pd.isna(value) else value
            for key, value in raw.items()
        }
        records.append(validate_record(raw, index + 2))
    return records


def import_excel(file_path, replace=False, make_backup=True):
    if not replace:
        raise ValueError("导入会替换现有数据，请显式传入 --replace")
    records = load_excel(file_path)
    return replace_watersheds(create_app(), records, make_backup=make_backup)


def main(argv=None):
    parser = argparse.ArgumentParser(description="导入 CONCN 流域 Excel 数据")
    parser.add_argument("file", help="Excel 文件路径")
    parser.add_argument("--replace", action="store_true", help="确认替换现有流域数据")
    parser.add_argument("--no-backup", action="store_true", help="不备份当前 SQLite 数据库")
    args = parser.parse_args(argv)
    count = import_excel(args.file, replace=args.replace, make_backup=not args.no_backup)
    print(f"成功导入 {count} 条记录")


if __name__ == "__main__":
    main()
