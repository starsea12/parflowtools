#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从 Excel 文件导入流域数据到数据库
Excel 列名：编号, 级别, 所属地区, 经度, 纬度, 面积
"""
import os
import sys
import pandas as pd
from app import create_app
from models import db, Watershed

# ===== 修改为你的文件路径 =====
EXCEL_FILE_PATH = '/data/wangzihan-data/backend/watershed_info.xlsx'
# ==============================

def clean_id(raw):
    """
    清理科学计数法（如 1.05201E+13）为完整的数字字符串
    """
    if pd.isna(raw):
        return None
    raw = str(raw).strip()
    if 'E' in raw or 'e' in raw:
        try:
            # 转换为浮点数再转为整数字符串（可能丢失精度，但能恢复大部分）
            num = int(float(raw))
            return str(num)
        except:
            return raw
    # 如果包含小数点（如 '01000000000000.0'），去掉小数点
    if '.' in raw:
        raw = raw.split('.')[0]
    return raw

def import_excel(file_path):
    if not os.path.exists(file_path):
        print(f"错误：文件 {file_path} 不存在")
        sys.exit(1)

    app = create_app()
    with app.app_context():
        # 清空现有数据（方案一的核心）
        db.session.query(Watershed).delete()
        db.session.commit()
        print("已清空原有数据")

        # 读取 Excel，强制将“编号”列作为字符串读取
        df = pd.read_excel(file_path, dtype={'编号': str}, engine='openpyxl')
        print("检测到的列名：", df.columns.tolist())

        # 检查必要的列是否存在
        required_cols = ['编号', '级别', '所属地区', '经度', '纬度', '面积']
        for col in required_cols:
            if col not in df.columns:
                print(f"错误：Excel 中缺少 '{col}' 列")
                sys.exit(1)

        # 清理编号列：处理科学计数法，去除小数点
        df['编号'] = df['编号'].apply(clean_id)

        # 去除重复的编号（保留第一次出现的行）
        original_count = len(df)
        df = df.drop_duplicates(subset=['编号'], keep='first')
        print(f"去重前 {original_count} 条，去重后 {len(df)} 条")

        # 删除编号为空的行
        df = df[df['编号'].notna() & (df['编号'] != '')]
        print(f"删除空编号后剩余 {len(df)} 条")

        count = 0
        for index, row in df.iterrows():
            raw_id = str(row['编号']).strip()
            # 再次确保没有多余符号
            if '.' in raw_id:
                raw_id = raw_id.split('.')[0]

            watershed = Watershed(
                id=raw_id,
                name='',
                level=int(row['级别']),
                region=row['所属地区'].strip(),
                lng=float(row['经度']) if pd.notna(row['经度']) else None,
                lat=float(row['纬度']) if pd.notna(row['纬度']) else None,
                area=float(row['面积']) if pd.notna(row['面积']) else None,
                description=''
            )
            db.session.add(watershed)
            count += 1
            if count % 1000 == 0:
                print(f"已处理 {count} 条")
                db.session.commit()  # 每1000条提交一次，避免一次性提交大量数据

        db.session.commit()
        print(f"成功导入 {count} 条记录")

if __name__ == '__main__':
    import_excel(EXCEL_FILE_PATH)