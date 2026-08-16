import os
from pathlib import Path

# 获取当前文件（config.py）所在目录，即 backend 根目录
BASE_DIR = Path(__file__).resolve().parent

class Config:
    DEBUG = os.getenv('FLASK_DEBUG', '').lower() in {'1', 'true', 'yes'}

    # 数据库 URI（SQLite）
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{BASE_DIR / "instance" / "watershed.db"}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 每次下载使用独立任务目录，避免并发请求互相覆盖
    JOB_ROOT = Path(os.getenv('CONCN_JOB_ROOT', BASE_DIR / 'jobs'))
    MAX_BATCH_DOWNLOADS = int(os.getenv('CONCN_MAX_BATCH_DOWNLOADS', '10'))
    ALLOWED_ORIGINS = [
        origin.strip()
        for origin in os.getenv('CONCN_ALLOWED_ORIGINS', '*').split(',')
        if origin.strip()
    ]
    
    # 最大上传/下载文件大小（100MB）
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024

    # 边界缓存目录
    BOUNDARY_CACHE_DIR = BASE_DIR / 'boundary_cache'

    # SQLite 并发: 4 个 gunicorn worker 共享一个 db 文件,
    # 忙等待最长 30s(sqlite3 默认 5s),避免并发写(登录/登出/下载审计)时 "database is locked"
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {'timeout': 30},
    }

    # 登录 token 有效期(天),签发时写入 auth_tokens.expires_at
    TOKEN_EXPIRY_DAYS = 7

    # 登录失败锁定:连续失败 MAX_LOGIN_FAILURES 次后锁定 LOGIN_LOCK_MINUTES 分钟
    MAX_LOGIN_FAILURES = 5
    LOGIN_LOCK_MINUTES = 15

    # 忘记密码重置码有效期(分钟)
    RESET_CODE_EXPIRY_MINUTES = 30

    # SHP 文件目录（默认 Linux 服务器路径，本地开发设环境变量 CONCN_SHP_DIR 覆盖）
    SHP_DIR = os.getenv(
        'CONCN_SHP_DIR',
        '/data/share/parflow-group/CONCN_Subbasins_Map/PFBAS/shp',
    )

    # Flask 托管前端时使用；固定集群路径保留为默认值
    DIST_DIR = Path(os.getenv(
        'CONCN_DIST_DIR',
        '/data/wangzihan-data/parflow-website/dist',
    ))
