import os
from pathlib import Path

# 获取当前文件（config.py）所在目录，即 backend 根目录
BASE_DIR = Path(__file__).resolve().parent

class Config:
    # 数据库 URI（SQLite）
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{BASE_DIR / "instance" / "watershed.db"}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 临时文件保存目录（用于存放裁剪结果打包文件）
    UPLOAD_FOLDER = BASE_DIR / 'uploads'
    
    # 最大上传/下载文件大小（100MB）
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024

    # 边界缓存目录
    BOUNDARY_CACHE_DIR = BASE_DIR / 'boundary_cache'

    # SHP 文件目录（默认 Linux 服务器路径，本地开发设环境变量 SHP_DIR 覆盖）
    SHP_DIR = os.getenv('SHP_DIR', '/data/share/parflow-group/CONCN_Subbasins_Map/PFBAS/shp')