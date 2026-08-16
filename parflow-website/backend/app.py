import os
import re
import secrets
import time
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from flask import Flask, g, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from models import db, Watershed, User, AuthToken, PasswordResetToken, DownloadLog
from clip_worker import run_clip
from boundary_service import get_boundaries


def _migrate_auth_columns():
    """给已存在的 users/auth_tokens 表补充新增列(SQLite ALTER TABLE,幂等,失败不阻塞启动)。"""
    from sqlalchemy import inspect, text
    insp = inspect(db.engine)
    for table, column, ddl in [
        ('users', 'failed_attempts', 'ALTER TABLE users ADD COLUMN failed_attempts INTEGER NOT NULL DEFAULT 0'),
        ('users', 'locked_until', 'ALTER TABLE users ADD COLUMN locked_until DATETIME'),
        ('auth_tokens', 'expires_at', 'ALTER TABLE auth_tokens ADD COLUMN expires_at DATETIME'),
    ]:
        try:
            if table in insp.get_table_names() and column not in {c['name'] for c in insp.get_columns(table)}:
                db.session.execute(text(ddl))
        except Exception as e:
            print(f'[migrate] 补充列 {table}.{column} 失败(可能已存在): {e}')
    db.session.commit()

def _init_database(retries=10, delay=2):
    """建表初始化,带并发竞争重试。
    gunicorn -w 4 首次启动时,多个 worker 同时执行 create_all:
    各自先查 has_table(False) 再建表 → 只有第一个 CREATE TABLE 成功,
    其余报 'table users already exists' → worker 启动失败 → 整个 gunicorn 崩溃
    (本地实测 4 进程同时建表 75% 失败,与服务器 08-14 崩溃一致)。
    重试时表已存在,has_table 检查直接通过;锁冲突等待后重试。"""
    from sqlalchemy.exc import OperationalError
    for attempt in range(1, retries + 1):
        try:
            db.create_all()
            _migrate_auth_columns()
            return
        except OperationalError as e:
            msg = str(e).lower()
            if 'already exists' in msg or 'locked' in msg:
                print(f'[init] 建表竞争或锁冲突,{delay}s 后重试({attempt}/{retries}): {e}')
                time.sleep(delay)
                continue
            raise
    raise RuntimeError('数据库初始化失败: 多次重试后仍失败')

def _validate_password(password):
    """密码规则:8-16 位,且必须同时包含字母和数字。合法返回 None,否则返回错误消息。"""
    if not (8 <= len(password) <= 16):
        return '密码长度需为8-16位'
    if not re.search(r'[A-Za-z]', password) or not re.search(r'[0-9]', password):
        return '密码必须同时包含字母和数字'
    return None


def create_app():
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)
    app.config['JSON_AS_ASCII'] = False

    database_path = Path(app.config['SQLALCHEMY_DATABASE_URI'].removeprefix('sqlite:///'))
    database_path.parent.mkdir(parents=True, exist_ok=True)
    Path(app.config['JOB_ROOT']).mkdir(parents=True, exist_ok=True)
    Path(app.config['BOUNDARY_CACHE_DIR']).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    CORS(app, resources={r'/api/*': {'origins': app.config['ALLOWED_ORIGINS']}})

    # 每个 gunicorn worker 启动时都执行建表;带重试避免并发建表竞争(08-14 崩溃修复)
    with app.app_context():
        _init_database()

    # ---------- 用户认证 API ----------
    def current_user():
        """从 Authorization: Bearer <token> 解析当前登录用户，未登录/过期返回 None。
        同一请求内结果缓存在 flask.g,多次调用只查一次库。"""
        if '_current_user' in g:
            return g._current_user
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return None
        token = auth[7:].strip()
        if not token:
            return None
        auth_token = AuthToken.query.filter_by(token=token).first()
        if not auth_token:
            return None
        # token 过期(或无过期时间的旧 token):删除该行并视为未登录
        if auth_token.expires_at is None or auth_token.expires_at < datetime.utcnow():
            db.session.delete(auth_token)
            db.session.commit()
            return None
        user = User.query.get(auth_token.user_id)
        g._current_user = user
        return user

    def login_required(f):
        """数据接口鉴权装饰器：未登录返回 401"""
        @wraps(f)
        def wrapper(*args, **kwargs):
            if current_user() is None:
                return jsonify({'error': '未登录或登录已过期'}), 401
            return f(*args, **kwargs)
        return wrapper

    def issue_token(user):
        """签发新 token 并设置过期时间(TOKEN_EXPIRY_DAYS 天)"""
        token = secrets.token_hex(32)
        expires_at = datetime.utcnow() + timedelta(days=app.config['TOKEN_EXPIRY_DAYS'])
        db.session.add(AuthToken(token=token, user_id=user.id, expires_at=expires_at))
        db.session.commit()
        return token

    def cleanup_expired_tokens():
        """顺手清理已过期的 token 行,防止 auth_tokens 无限增长"""
        AuthToken.query.filter(AuthToken.expires_at < datetime.utcnow()).delete()
        db.session.commit()

    @app.route('/api/register', methods=['POST'])
    def register():
        data = request.get_json(silent=True) or {}
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''
        email = (data.get('email') or '').strip()

        if not (4 <= len(username) <= 16):
            return jsonify({'error': '用户名长度为4-16位'}), 400
        pw_err = _validate_password(password)
        if pw_err:
            return jsonify({'error': pw_err}), 400
        if not email or not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            return jsonify({'error': '请输入正确的邮箱格式'}), 400
        if User.query.filter_by(username=username).first():
            return jsonify({'error': '该用户名已被占用，请更换'}), 409

        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            email=email,
        )
        db.session.add(user)
        db.session.commit()

        # 注册成功直接登录:顺手清理过期 token,再签发新 token
        cleanup_expired_tokens()
        token = issue_token(user)
        return jsonify({'token': token, 'username': user.username, 'email': user.email})

    @app.route('/api/login', methods=['POST'])
    def login():
        data = request.get_json(silent=True) or {}
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''

        user = User.query.filter_by(username=username).first()
        now = datetime.utcnow()

        # 账号锁定中:直接拒绝,不校验密码
        if user and user.locked_until and user.locked_until > now:
            return jsonify({'error': f'失败次数过多，账号已锁定 {app.config["LOGIN_LOCK_MINUTES"]} 分钟，请稍后再试'}), 429

        if not user or not check_password_hash(user.password_hash, password):
            # 只有用户真实存在才计数(不泄露用户名是否存在;不存在的用户一律通用提示)
            if user:
                user.failed_attempts = (user.failed_attempts or 0) + 1
                if user.failed_attempts >= app.config['MAX_LOGIN_FAILURES']:
                    user.locked_until = now + timedelta(minutes=app.config['LOGIN_LOCK_MINUTES'])
                    user.failed_attempts = 0  # 锁定期间清零,解锁后重新计数
                    db.session.commit()
                    return jsonify({'error': f'失败次数过多，账号已锁定 {app.config["LOGIN_LOCK_MINUTES"]} 分钟，请稍后再试'}), 429
                db.session.commit()
                remaining = app.config['MAX_LOGIN_FAILURES'] - user.failed_attempts
                return jsonify({'error': f'用户名或密码错误，还可尝试 {remaining} 次'}), 401
            return jsonify({'error': '用户名或密码错误'}), 401

        # 登录成功:重置失败计数,清理过期 token,签发新 token
        user.failed_attempts = 0
        user.locked_until = None
        cleanup_expired_tokens()
        token = issue_token(user)
        return jsonify({'token': token, 'username': user.username, 'email': user.email})

    @app.route('/api/me', methods=['GET'])
    def me():
        user = current_user()
        if not user:
            return jsonify({'error': '未登录或登录已过期'}), 401
        return jsonify(user.to_dict())

    @app.route('/api/logout', methods=['POST'])
    def logout():
        auth = request.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            token = auth[7:].strip()
            AuthToken.query.filter_by(token=token).delete()
            db.session.commit()
        return jsonify({'ok': True})

    # ---------- 用户中心:修改密码/邮箱/用户名 ----------
    @app.route('/api/me/password', methods=['PUT'])
    @login_required
    def change_password():
        user = current_user()
        data = request.get_json(silent=True) or {}
        old_password = data.get('old_password') or ''
        new_password = data.get('new_password') or ''

        if not check_password_hash(user.password_hash, old_password):
            return jsonify({'error': '原密码错误'}), 400
        pw_err = _validate_password(new_password)
        if pw_err:
            return jsonify({'error': pw_err}), 400

        user.password_hash = generate_password_hash(new_password)
        # 改密码后吊销该用户除当前 token 外的所有登录(其他设备需重新登录)
        current_token = None
        auth = request.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            current_token = auth[7:].strip()
        AuthToken.query.filter(AuthToken.user_id == user.id, AuthToken.token != current_token).delete()
        db.session.commit()
        return jsonify({'ok': True, 'message': '密码修改成功'})

    @app.route('/api/me/email', methods=['PUT'])
    @login_required
    def change_email():
        user = current_user()
        data = request.get_json(silent=True) or {}
        email = (data.get('email') or '').strip()
        password = data.get('password') or ''

        # 邮箱是忘记密码的验证凭据,修改必须验证当前密码
        if not email or not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            return jsonify({'error': '请输入正确的邮箱格式'}), 400
        if not check_password_hash(user.password_hash, password):
            return jsonify({'error': '密码错误'}), 400

        user.email = email
        db.session.commit()
        return jsonify({'ok': True, 'email': email, 'message': '邮箱修改成功'})

    @app.route('/api/me/username', methods=['PUT'])
    @login_required
    def change_username():
        user = current_user()
        data = request.get_json(silent=True) or {}
        username = (data.get('username') or '').strip()

        if not (4 <= len(username) <= 16):
            return jsonify({'error': '用户名长度为4-16位'}), 400
        if User.query.filter_by(username=username).first():
            return jsonify({'error': '该用户名已被占用，请更换'}), 409

        user.username = username
        db.session.commit()
        return jsonify({'ok': True, 'username': username, 'message': '用户名修改成功'})

    # ---------- 忘记密码(重置码方式) ----------
    @app.route('/api/forgot-password', methods=['POST'])
    def forgot_password():
        """忘记密码第一步:验证用户名+注册邮箱,签发重置码。
        服务器没有 SMTP,重置码直接返回给前端展示(用户填邮箱时自己能看到);
        后续接入邮件服务后只需把返回改为发邮件。"""
        data = request.get_json(silent=True) or {}
        username = (data.get('username') or '').strip()
        email = (data.get('email') or '').strip()

        if not username or not email:
            return jsonify({'error': '请输入用户名和注册邮箱'}), 400

        user = User.query.filter_by(username=username).first()
        # 用户不存在或邮箱不匹配:统一提示,不泄露用户名/邮箱是否真实存在
        if not user or (user.email or '').strip().lower() != email.lower():
            return jsonify({'error': '用户名与注册邮箱不匹配'}), 400

        # 重新申请时覆盖旧码(一个用户同时只有一个有效重置码)
        code = secrets.token_hex(4)  # 8位 hex
        PasswordResetToken.query.filter_by(user_id=user.id).delete()
        db.session.add(PasswordResetToken(
            user_id=user.id,
            code=code,
            expires_at=datetime.utcnow() + timedelta(minutes=app.config['RESET_CODE_EXPIRY_MINUTES']),
        ))
        db.session.commit()
        return jsonify({
            'code': code,
            'expires_in_minutes': app.config['RESET_CODE_EXPIRY_MINUTES'],
        })

    @app.route('/api/reset-password', methods=['POST'])
    def reset_password():
        """忘记密码第二步:凭重置码设置新密码。"""
        data = request.get_json(silent=True) or {}
        username = (data.get('username') or '').strip()
        code = (data.get('code') or '').strip()
        new_password = data.get('new_password') or ''

        if not username or not code:
            return jsonify({'error': '缺少参数'}), 400
        pw_err = _validate_password(new_password)
        if pw_err:
            return jsonify({'error': pw_err}), 400

        user = User.query.filter_by(username=username).first()
        reset = PasswordResetToken.query.filter_by(code=code).first()
        if not user or not reset or reset.user_id != user.id or reset.expires_at < datetime.utcnow():
            return jsonify({'error': '重置码无效或已过期'}), 400

        user.password_hash = generate_password_hash(new_password)
        # 解锁账号并清零失败计数(找回密码常用于账号被锁定的场景)
        user.failed_attempts = 0
        user.locked_until = None
        # 密码已重置:吊销该用户所有登录 token,旧会话全部失效
        AuthToken.query.filter_by(user_id=user.id).delete()
        db.session.delete(reset)
        db.session.commit()
        return jsonify({'ok': True, 'message': '密码重置成功，请使用新密码登录'})

    # ---------- API 路由 ----------
    @app.route('/api/config', methods=['GET'])
    def public_config():
        return jsonify({
            'maxBatchDownloads': app.config['MAX_BATCH_DOWNLOADS'],
        })

    @app.route('/api/watersheds', methods=['GET'])
    @login_required
    def search_watersheds():
        keyword = request.args.get('keyword', '').strip()
        region = request.args.get('region', '').strip()
        level = request.args.get('level', type=int)

        query = Watershed.query
        if keyword:
            query = query.filter(
                (Watershed.id.contains(keyword)) | (Watershed.name.contains(keyword))
            )
        if region:
            query = query.filter(Watershed.region == region)
        if level is not None:
            query = query.filter(Watershed.level == level)

        results = query.all()
        return jsonify([w.to_dict() for w in results])

    @app.route('/api/watersheds/<id>', methods=['GET'])
    @login_required
    def get_watershed(id):
        watershed = Watershed.query.get(id)
        if not watershed:
            return jsonify({'error': '流域不存在'}), 404
        return jsonify(watershed.to_dict())

    @app.route('/api/download', methods=['POST'])
    @login_required
    def download_data():
        data = request.get_json()
        if not data or 'ids' not in data:
            return jsonify({'error': '缺少 ids 参数'}), 400

        ids = data.get('ids')
        if isinstance(ids, str):
            ids = [ids]
        elif isinstance(ids, list):
            ids = [str(item) for item in ids]
        else:
            return jsonify({'error': 'ids 必须是字符串或列表'}), 400

        ids = [i.strip() for i in ids if i.strip()]
        ids = list(dict.fromkeys(ids))
        if not ids:
            return jsonify({'error': 'ids 不能为空'}), 400
        if len(ids) > app.config['MAX_BATCH_DOWNLOADS']:
            return jsonify({
                'error': f'单次最多下载 {app.config["MAX_BATCH_DOWNLOADS"]} 个流域'
            }), 400

        existing_ids = [w.id for w in Watershed.query.filter(Watershed.id.in_(ids)).all()]
        invalid_ids = [i for i in ids if i not in existing_ids]
        if invalid_ids:
            return jsonify({'error': f'以下编号不存在: {invalid_ids}'}), 404

        try:
            zip_path = run_clip(ids, Path(app.config['JOB_ROOT']))
        except Exception:
            app.logger.exception('裁剪或打包失败，流域编号: %s', ids)
            return jsonify({'error': '裁剪或打包失败，请联系管理员查看服务日志'}), 500

        # 下载成功:写入审计日志(谁/何时/下载了什么/多大)
        user = current_user()
        try:
            db.session.add(DownloadLog(
                user_id=user.id,
                username=user.username,
                watershed_ids=','.join(ids),
                file_size=os.path.getsize(zip_path),
            ))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f'[audit] 下载日志写入失败: {e}')

        return send_file(zip_path, as_attachment=True)

    @app.route('/api/downloads', methods=['GET'])
    @login_required
    def my_downloads():
        """当前用户的下载历史(最近优先)"""
        user = current_user()
        try:
            limit = request.args.get('limit', type=int)
        except ValueError:
            limit = None
        limit = max(1, min(limit or 50, 200))  # 负数 limit 在 SQLite 里表示不限制,夹到 [1, 200]
        logs = (
            DownloadLog.query.filter_by(user_id=user.id)
            .order_by(DownloadLog.created_at.desc(), DownloadLog.id.desc())
            .limit(limit)
            .all()
        )
        return jsonify([log.to_dict() for log in logs])

    # ---------- 流域边界 API ----------
    @app.route('/api/boundaries', methods=['GET'])
    @login_required
    def boundaries():
        """返回流域边界 GeoJSON（按级别或按 id 筛选）"""
        return get_boundaries()

    # ---------- 前端静态文件服务 ----------
    dist_dir = Path(app.config['DIST_DIR'])

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        # 如果是 API 请求，不处理（API 路由优先）
        if path.startswith('api/'):
            return '', 404

        # 尝试返回静态文件
        full_path = dist_dir / path
        if path != '' and os.path.exists(full_path) and os.path.isfile(full_path):
            return send_from_directory(dist_dir, path)
        else:
            # 返回 index.html（支持 Vue Router）
            return send_from_directory(dist_dir, 'index.html')

    return app


# ---------- 创建应用实例（供 gunicorn 使用） ----------
app = create_app()

# ---------- 直接运行（开发/测试） ----------
if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'], host='0.0.0.0', port=50001)
