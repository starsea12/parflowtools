#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
导入 CSV 文件中的流域数据到数据库
支持处理科学计数法格式的 ID（如 1.05201E+13）
"""
import csv
import os
import sys
from app import create_app
from models import db, Watershed

CSV_FILE_PATH = '/data/wangzihan-data/backend/watershed_info.xlsx'   # 修改为实际路径

def clean_id(raw):
    """尝试将科学计数法字符串还原为14位字符串"""
    raw = raw.strip()
    if 'E' in raw or 'e' in raw:
        # 转换为浮点数再转为整数，但可能丢失精度
        try:
            num = int(float(raw))
            return str(num)
        except:
            return raw
    return raw

def import_csv(file_path):
    if not os.path.exists(file_path):
        print(f"错误：文件 {file_path} 不存在")
        sys.exit(1)

    app = create_app()
    with app.app_context():
        # 清空现有数据
        db.session.query(Watershed).delete()
        db.session.commit()

        with open(file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            raw_fieldnames = reader.fieldnames
            clean_to_raw = {}
            for name in raw_fieldnames:
                clean_name = name.strip()
                clean_to_raw[clean_name] = name
            print("检测到的列名（清理后）：", list(clean_to_raw.keys()))

            count = 0
            for row in reader:
                id_key = clean_to_raw.get('编号')
                if id_key is None:
                    print("错误：CSV 中缺少 '编号' 列")
                    break

                raw_id = row.get(id_key, '').strip()
                if not raw_id:
                    continue

                # 清理科学计数法
                cleaned_id = clean_id(raw_id)

                watershed = Watershed(
                    id=cleaned_id,
                    name='',
                    level=int(float(row[clean_to_raw['级别']])),
                    region=row[clean_to_raw['所属地区']].strip(),
                    lng=float(row[clean_to_raw['经度']]) if row.get(clean_to_raw['经度']) else None,
                    lat=float(row[clean_to_raw['纬度']]) if row.get(clean_to_raw['纬度']) else None,
                    area=float(row[clean_to_raw['面积']]) if row.get(clean_to_raw['面积']) else None,
                    description=''
                )
                db.session.add(watershed)
                count += 1
                if count % 1000 == 0:
                    print(f"已处理 {count} 条")
            db.session.commit()
            print(f"成功导入 {count} 条记录")

if __name__ == '__main__':
    import_csv(CSV_FILE_PATH)