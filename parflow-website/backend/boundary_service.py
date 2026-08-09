"""
流域边界服务：从 PFBAS shp 文件读取、重投影为 WGS84，缓存为 GeoJSON，
提供全量或按 id 筛选的边界数据，供前端天地图叠加显示。
"""
import gzip
import json
import os
from pathlib import Path
import geopandas as gpd
from flask import jsonify, request, current_app


# ---- 缓存管理 ----

def _cache_path(level, cache_dir):
    """返回某级别缓存 GeoJSON 文件路径"""
    return Path(cache_dir) / f"PFBAS{level}.geojson"


def _shp_path(level, shp_dir):
    """返回某级别原始 shp 文件路径"""
    return Path(shp_dir) / f"PFBAS{level}.shp"


def _build_cache(level, shp_dir, cache_dir):
    """首次加载：读取 shp → 重投影 WGS84 → 写 GeoJSON 缓存 → 返回 GeoDataFrame"""
    shp = _shp_path(level, shp_dir)
    if not shp.exists():
        raise FileNotFoundError(f"未找到 SHP 文件: {shp}")

    gdf = gpd.read_file(shp)

    # 简化前先算真实面积（原始投影 ESRI:102012 为米制，.area 即 m²；
    # 若先重投影到经纬度再算会失真，因此必须在重投影之前计算）
    areas_m2 = None
    if gdf.crs is not None and gdf.crs.is_projected:
        areas_m2 = gdf.geometry.area

    # 重投影到 WGS84 经纬度（天地图使用 EPSG:4326）
    if gdf.crs is not None:
        gdf = gdf.to_crs("EPSG:4326")

    # 对大数据级别应用几何简化（减少前端渲染压力）
    # 精细度优先策略（用户确认：与加载时间冲突时优先精细度）：
    # 10 级: 统一公差 0.002 → 保留 98% 顶点，gz 11.9MB（原始 shp 顶点本就不多）
    # 12/14 级: 面积自适应 —— 小流域用小公差保形状，大流域用大公差压体积
    #   <100 km² → 0.001, 100~500 km² → 0.002, >500 km² → 0.005
    #   （0.001 度 ≈ 100m，已接近原始 shp 精度；实测保留率：
    #     10 级 98% / 12 级 83%(median 78) / 14 级 98%(median 39)）
    # 实测体积: 10级 gz 11.9MB; 12级 946k顶点/43.9MB raw/14.9MB gz; 14级 2.08M顶点/100.4MB raw/40.2MB gz
    ADAPTIVE_TOLS = {
        12: (0.001, 0.002, 0.005),
        14: (0.001, 0.002, 0.005),
    }
    simplify_tolerance = {10: 0.002}.get(level, 0)
    if simplify_tolerance > 0:
        gdf["geometry"] = gdf["geometry"].simplify(tolerance=simplify_tolerance, preserve_topology=True)
    elif level in ADAPTIVE_TOLS and areas_m2 is not None:
        s_tol, m_tol, l_tol = ADAPTIVE_TOLS[level]
        gdf["geometry"] = [
            geom.simplify(
                s_tol if area < 100e6 else (m_tol if area < 500e6 else l_tol),
                preserve_topology=True,
            )
            for geom, area in zip(gdf["geometry"], areas_m2)
        ]

    # 确保缓存目录存在
    Path(cache_dir).mkdir(parents=True, exist_ok=True)

    # 写入缓存
    cache_file = _cache_path(level, cache_dir)
    gdf.to_file(cache_file, driver="GeoJSON", encoding="utf-8")
    # 预压缩 gzip 缓存（请求时直接返回 .gz 字节，省去实时压缩 CPU）
    try:
        with open(cache_file, "rb") as f:
            raw = f.read()
        with open(str(cache_file) + ".gz", "wb") as f:
            f.write(gzip.compress(raw, compresslevel=1))
    except Exception as e:
        print(f"[边界缓存] gzip 预压缩失败（不影响主缓存）: {e}")
    print(f"[边界缓存] 已生成: {cache_file} ({gdf.shape[0]} 个要素)")

    return gdf


def _load_cached(level, cache_dir):
    """从缓存文件加载 GeoDataFrame"""
    cache_file = _cache_path(level, cache_dir)
    if not cache_file.exists():
        return None
    return gpd.read_file(cache_file)


# ---- API 逻辑 ----

def get_boundaries():
    """
    GET /api/boundaries?level=X              → 返回该级别全量边界
    GET /api/boundaries?level=X&ids=a,b,c    → 只返回指定 id 的边界（搜索结果高亮）
    """
    level_str = request.args.get("level", "").strip()
    ids_str = request.args.get("ids", "").strip()

    if not level_str:
        return jsonify({"error": "缺少 level 参数"}), 400

    try:
        level = int(level_str)
    except ValueError:
        return jsonify({"error": "level 必须为整数"}), 400

    if level < 2 or level > 14 or level % 2 != 0:
        return jsonify({"error": "level 必须为 2~14 之间的偶数"}), 400

    shp_dir = current_app.config.get("SHP_DIR", "")
    cache_dir = current_app.config.get("BOUNDARY_CACHE_DIR", "")

    # 解析要筛选的 id 列表
    requested_ids = None
    if ids_str:
        requested_ids = [i.strip() for i in ids_str.split(",") if i.strip()]
        if not requested_ids:
            requested_ids = None

    try:
        # 无 id 筛选的完整请求：直接返回缓存文件字节（跳过 gpd 解析 + 逐特征序列化）
        if requested_ids is None:
            cache_file = _cache_path(level, cache_dir)
            if cache_file.exists():
                # 支持 gzip 时优先返回预压缩的 .gz（体积约为原始 1/3，传输更快）
                if "gzip" in request.headers.get("Accept-Encoding", "").lower():
                    gz_file = Path(str(cache_file) + ".gz")
                    if gz_file.exists():
                        return current_app.response_class(
                            gz_file.read_bytes(),
                            mimetype="application/json",
                            headers={"Content-Encoding": "gzip"},
                        )
                return current_app.response_class(
                    cache_file.read_bytes(), mimetype="application/json"
                )
            # 无缓存：生成（含 .gz 预压缩）
            gdf = _build_cache(level, shp_dir, cache_dir)
            cache_file = _cache_path(level, cache_dir)
            if "gzip" in request.headers.get("Accept-Encoding", "").lower():
                return current_app.response_class(
                    Path(str(cache_file) + ".gz").read_bytes(),
                    mimetype="application/json",
                    headers={"Content-Encoding": "gzip"},
                )
            return current_app.response_class(
                cache_file.read_bytes(), mimetype="application/json"
            )

        # 有 id 筛选：走原有路径（解析 + 过滤 + 序列化）
        gdf = _load_cached(level, cache_dir)
        if gdf is None:
            gdf = _build_cache(level, shp_dir, cache_dir)

        # 如果有 id 筛选，过滤
        id_column = "PFBAS_ID" if "PFBAS_ID" in gdf.columns else gdf.columns[0]
        if requested_ids is not None:
            gdf = gdf[gdf[id_column].astype(str).isin(requested_ids)]

        # 返回简化版 FeatureCollection（仅保留必要字段，减少传输体积）
        features = []
        for _, row in gdf.iterrows():
            props = {}
            for col in gdf.columns:
                if col != "geometry":
                    val = row[col]
                    # 转换 numpy 类型为 Python 原生类型
                    if hasattr(val, "item"):
                        val = val.item()
                    props[col] = val

            geom_json = json.loads(row.geometry._export_into_memory()) if hasattr(
                row.geometry, "_export_into_memory"
            ) else None

            if geom_json is None:
                # 兼容 shapely 不同版本的序列化方式
                from shapely import to_geojson as _shapely_to_geojson
                geom_json = json.loads(_shapely_to_geojson(row.geometry))

            features.append({
                "type": "Feature",
                "properties": props,
                "geometry": geom_json,
            })

        result = {"type": "FeatureCollection", "features": features}
        # 紧凑 JSON（jsonify 在 debug 模式下会缩进美化，体积膨胀约 2 倍）
        return current_app.response_class(
            json.dumps(result, ensure_ascii=False, separators=(",", ":")),
            mimetype="application/json",
        )

    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"获取边界数据失败: {str(e)}"}), 500
