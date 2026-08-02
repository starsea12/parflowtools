#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自动运行程序一（生成掩膜）和程序二（裁剪PFB）
根据 PFBASID 自动识别对应的 PFBASn.shp 和 PFBASn.tif 文件
直接调用函数，无需 subprocess
支持裁剪多个 PFB 文件，输出文件名自动为“核心名称.流域编号.pfb”
裁剪完成后，将 mask.tif 转换为 mask.pfb，再根据 mask.pfb 生成 VTK 和 PFSOL 文件（按流域编码命名）
完成后自动删除所有 .dist 文件及 pos.json
输出文件统一存放在 outputs/<流域编号>/ 目录下
mask 文件命名为 mask.<流域编号>.tif 和 mask.<流域编号>.pfb
"""

import os
import sys
import shutil          # 新增：用于删除目录
import subprocess
import numpy as np
import rasterio

# 处理相对导入与直接运行的情况
try:
    # 作为包的一部分时使用相对导入
    from .generate_mask import generate_mask
    from .crop_pfb import crop_pfb
except ImportError:
    # 直接运行脚本时使用绝对导入（假设脚本与模块在同一目录）
    from generate_mask import generate_mask
    from crop_pfb import crop_pfb

from parflow.tools.io import read_pfb, write_pfb

# ==================== 用户配置 ====================
SHP_DIR = "/data/share/parflow-group/CONCN_Subbasins_Map/PFBAS/shp"
TIF_DIR = "/data/share/parflow-group/CONCN_Subbasins_Map/PFBAS/geotiff"
INPUT_PFB_DIR = "/data/share/parflow-group/CONCN1.1/inputs"

# 输出基础目录：默认当前工作目录下的 outputs，可通过环境变量 OUTPUT_DIR 覆盖
DEFAULT_BASE_OUTPUT_DIR = os.path.join(os.getcwd(), "outputs")
BASE_OUTPUT_DIR = os.getenv("OUTPUT_DIR", DEFAULT_BASE_OUTPUT_DIR)
os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)

FIELD_NAME = "PFBAS_ID"
EXPAND = 1

PFMASK_CMD = "/data/software/parflow-gnu13/parflow-3.13.0/bin/pfmask-to-pfsol"
BOTTOM_PATCH_LABEL = 2
SIDE_PATCH_LABEL = 3
Z_TOP = 2000.0
Z_BOTTOM = 0.0

PFB_INPUTS = [
    "CHN.slopex.2026.fix.pfb",
    "CHN.slopey.2026.fix.pfb",
    "Shangguan_300m_FBZ_fix.pfb",
    "CONCN_manning.fix.2026.pfb",
    "GLHYMPS1.0_multi_efold_fix.pfb"
]
# ====================================================


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def get_output_filename(input_filename, basin_code):
    mapping = {
        "CHN.slopex.2026.fix.pfb": "slopex",
        "CHN.slopey.2026.fix.pfb": "slopey",
        "Shangguan_300m_FBZ_fix.pfb": "bedrock",   # 修改为 bedrock
        "CONCN_manning.fix.2026.pfb": "manning",
        "GLHYMPS1.0_multi_efold_fix.pfb": "subsurface"
    }
    base_name = os.path.basename(input_filename)
    if base_name not in mapping:
        raise ValueError(f"未定义输出映射规则的文件: {base_name}")
    core_name = mapping[base_name]
    return f"{core_name}.{basin_code}.pfb"


def get_pfbas_level(pfbas_code):
    code_stripped = pfbas_code.rstrip('0')
    if not code_stripped:
        return 2
    level = len(code_stripped)
    if level % 2 != 0:
        level += 1
    if level < 2:
        level = 2
    if level > 14:
        level = 14
    return level


def convert_mask_tif_to_pfb(mask_tif_path, mask_pfb_path):
    """将 mask.tif 转换为 mask.pfb，保持原值：1=流域内，0=流域外"""
    with rasterio.open(mask_tif_path) as src:
        mask_2d = src.read(1).astype(np.uint8)   # 原值：1=内，0=外
    mask_3d = mask_2d[np.newaxis, :, :].astype(np.float64, order='C', copy=True)
    write_pfb(mask_pfb_path, mask_3d, dx=961.72, dy=961.72, dz=200, dist=False)
    print(f"[转换] 掩膜 TIF 已转换为 PFB: {mask_pfb_path} (流域内=1, 流域外=0)")


def generate_domain_files(mask_pfb_path, vtk_path, pfsol_path, output_dir):
    cmd = [
        PFMASK_CMD,
        "--mask", mask_pfb_path,
        "--vtk", vtk_path,
        "--pfsol", pfsol_path,
        "--bottom-patch-label", str(BOTTOM_PATCH_LABEL),
        "--side-patch-label", str(SIDE_PATCH_LABEL),
        "--z-top", str(Z_TOP),
        "--z-bottom", str(Z_BOTTOM)
    ]
    print(f"\n>>> 生成 VTK 和 PFSOL 文件（调用 pfmask-to-pfsol）")
    print(f"  执行命令: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True, cwd=output_dir,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       text=True)
        print(f"  成功生成: {vtk_path}\n            {pfsol_path}")
    except subprocess.CalledProcessError as e:
        print(f"  错误：命令执行失败，返回码 {e.returncode}")
        print(f"  错误输出: {e.stderr}")
        raise
    except FileNotFoundError:
        print(f"  错误：找不到命令 '{PFMASK_CMD}'，请检查路径")
        raise


def main():
    # 1. 输入流域编码
    pfbas_code = input("请输入14位流域编码（如01010105000000）: ").strip()
    if len(pfbas_code) != 14 or not pfbas_code.isdigit():
        print("错误：编码应为14位数字")
        sys.exit(1)

    # 2. 创建以流域编码命名的输出子目录
    output_dir = os.path.join(BASE_OUTPUT_DIR, pfbas_code)
    
    # ★★★ 新增：如果目录已存在，先删除整个目录（清理旧文件） ★★★
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
        print(f"[清理] 已删除旧输出目录: {output_dir}")
    
    ensure_dir(output_dir)
    print(f"[信息] 输出目录: {output_dir}")

    # 3. 前置检查：所有 PFB 输入文件是否存在
    missing_files = []
    for input_file in PFB_INPUTS:
        input_path = os.path.join(INPUT_PFB_DIR, input_file)
        if not os.path.exists(input_path):
            missing_files.append(input_path)
    if missing_files:
        print("错误：以下必需的输入 PFB 文件不存在，无法继续：")
        for f in missing_files:
            print(f"  {f}")
        sys.exit(1)
    print("[信息] 所有必需的 PFB 输入文件均存在。")

    # 4. 根据编码获取 Shapefile 和模板 TIF 路径
    level = get_pfbas_level(pfbas_code)
    print(f"[信息] 流域编码: {pfbas_code}")

    shp_path = os.path.join(SHP_DIR, f"PFBAS{level}.shp")
    tif_template = os.path.join(TIF_DIR, f"PFBAS{level}.tif")

    if not os.path.exists(shp_path):
        print(f"错误：找不到 Shapefile 文件 {shp_path}")
        sys.exit(1)
    if not os.path.exists(tif_template):
        print(f"错误：找不到模板 TIF 文件 {tif_template}")
        sys.exit(1)

    # 5. 定义输出文件路径（均在子目录内）
    mask_tif = os.path.join(output_dir, f"mask.{pfbas_code}.tif")
    mask_pfb = os.path.join(output_dir, f"mask.{pfbas_code}.pfb")
    pos_json = os.path.join(output_dir, f"pos.json")   # 保留 pos.json 名字，稍后删除
    out_vtk = os.path.join(output_dir, f"{pfbas_code}.vtk")
    out_pfsol = os.path.join(output_dir, f"{pfbas_code}.pfsol")

    # 6. 生成掩膜 TIF（程序一）
    print("\n>>> 程序一：生成掩膜和位置信息")
    generate_mask(
        shp_path=shp_path,
        code=pfbas_code,
        field=FIELD_NAME,
        tif_path=tif_template,
        out_mask_path=mask_tif,
        out_json_path=pos_json,
        expand=EXPAND,
        verbose=True
    )

    # 7. 转换掩膜 TIF 到 PFB（保持内1外0）
    print("\n>>> 转换掩膜：将 mask.tif 转换为 mask.pfb（保持内1外0）")
    convert_mask_tif_to_pfb(mask_tif, mask_pfb)

    # 8. 生成 VTK 和 PFSOL
    generate_domain_files(mask_pfb, out_vtk, out_pfsol, output_dir)

    # 9. 裁剪所有 PFB 文件
    print("\n>>> 程序二：裁剪 PFB 文件")
    for input_file in PFB_INPUTS:
        input_path = os.path.join(INPUT_PFB_DIR, input_file)
        output_file = get_output_filename(input_path, pfbas_code)
        output_path = os.path.join(output_dir, output_file)

        print(f"\n裁剪 {input_file} -> {output_file}")
        if not os.path.exists(input_path):
            print(f"警告：找不到输入文件 {input_path}，跳过（不应发生）")
            continue

        crop_pfb(
            pfb_path=input_path,
            mask_path=mask_tif,
            pos_json_path=pos_json,
            out_pfb_path=output_path,
            verbose=True
        )

    # 10. 清理 .dist 文件和 pos.json
    dist_files = [f for f in os.listdir(output_dir) if f.endswith('.dist')]
    for f in dist_files:
        os.remove(os.path.join(output_dir, f))
    if dist_files:
        print(f"已清理 {len(dist_files)} 个 .dist 文件")
    else:
        print("没有 .dist 文件需要清理")

    if os.path.exists(pos_json):
        os.remove(pos_json)
        print("已删除 pos.json 文件")
    else:
        print("pos.json 文件不存在，无需删除")

    # 11. 完成报告
    print("\n=== 全部完成 ===")
    print(f"掩膜 TIF: {mask_tif}")
    print(f"掩膜 PFB: {mask_pfb}")
    print(f"VTK 文件: {out_vtk}")
    print(f"PFSOL 文件: {out_pfsol}")
    for input_file in PFB_INPUTS:
        output_file = get_output_filename(input_file, pfbas_code)
        print(f"裁剪结果: {os.path.join(output_dir, output_file)}")


if __name__ == "__main__":
    main()