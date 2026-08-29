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
from models import db, Watershed, User, AuthToken, PasswordResetToken, DownloadLog, DownloadApplication, Notification, SiteSetting
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
        # 下载限制/管理员体系(2026-08-22)
        ('users', 'is_admin', 'ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0'),
        ('users', 'is_super_admin', 'ALTER TABLE users ADD COLUMN is_super_admin INTEGER NOT NULL DEFAULT 0'),
        ('users', 'download_limit', 'ALTER TABLE users ADD COLUMN download_limit INTEGER DEFAULT 1'),
        ('users', 'allowed_levels', "ALTER TABLE users ADD COLUMN allowed_levels VARCHAR(50) DEFAULT '8'"),
        ('download_logs', 'reason', 'ALTER TABLE download_logs ADD COLUMN reason TEXT'),
        # 科研单位(2026-08-29)
        ('users', 'institution', 'ALTER TABLE users ADD COLUMN institution VARCHAR(100)'),
        ('download_logs', 'institution', 'ALTER TABLE download_logs ADD COLUMN institution VARCHAR(100)'),
        ('download_applications', 'institution', 'ALTER TABLE download_applications ADD COLUMN institution VARCHAR(100)'),
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

def _bootstrap_super_admin():
    """最高管理员引导:系统尚无最高管理员时,把最早创建的管理员提升为最高管理员。
    幂等——已有最高管理员后不再执行(历史库首次部署此功能自动生效,无需手动 SQL)。"""
    if User.query.filter_by(is_super_admin=True).first() is not None:
        return
    first_admin = User.query.filter_by(is_admin=True).order_by(User.id.asc()).first()
    if not first_admin:
        return
    try:
        first_admin.is_super_admin = True
        db.session.commit()
        print(f'[bootstrap] 首个管理员 {first_admin.username}(id={first_admin.id}) 已成为最高管理员')
    except Exception as e:
        db.session.rollback()
        print(f'[bootstrap] 提升最高管理员失败(可能被其他 worker 抢先): {e}')

def _validate_password(password):
    """密码规则:8-16 位,且必须同时包含字母和数字。合法返回 None,否则返回错误消息。"""
    if not (8 <= len(password) <= 16):
        return '密码长度需为8-16位'
    if not re.search(r'[A-Za-z]', password) or not re.search(r'[0-9]', password):
        return '密码必须同时包含字母和数字'
    return None

def _user_download_used(user_id):
    """该用户累计下载过的流域编号集合(限额按 distinct 流域个数计)。"""
    used = set()
    logs = DownloadLog.query.filter_by(user_id=user_id).all()
    for log in logs:
        if log.watershed_ids:
            used.update(w.strip() for w in log.watershed_ids.split(',') if w.strip())
    return used

def _get_setting(key, fallback=None):
    """读取系统设置;未设置时返回 fallback(键在首次保存时才落库)。"""
    row = SiteSetting.query.get(key)
    return row.value if row else fallback

def _set_setting(key, value):
    """写入系统设置(键不存在则新建)。"""
    row = SiteSetting.query.get(key)
    if row is None:
        db.session.add(SiteSetting(key=key, value=value))
    else:
        row.value = value

def _parse_allowed_levels(user):
    """用户可下载的流域级别集合;空集 = 不限级别。"""
    raw = (user.allowed_levels or '').strip()
    if not raw:
        return set()
    levels = set()
    for part in raw.split(','):
        part = part.strip()
        if part.isdigit():
            levels.add(int(part))
    return levels

def _normalize_ids(data):
    """从请求体解析 ids:字符串或列表 → 去空/去重后的字符串列表;非法返回 None。"""
    if not data or 'ids' not in data:
        return None
    ids = data.get('ids')
    if isinstance(ids, str):
        ids = [ids]
    elif isinstance(ids, list):
        ids = [str(item) for item in ids]
    else:
        return None
    ids = [i.strip() for i in ids if i.strip()]
    return list(dict.fromkeys(ids))


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
        _bootstrap_super_admin()

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

    def admin_required(f):
        """管理员接口装饰器：未登录 401,非管理员 403"""
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                return jsonify({'error': '未登录或登录已过期'}), 401
            if not user.is_admin:
                return jsonify({'error': '无权限访问'}), 403
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

        # 新用户默认下载权限取系统设置(管理员可在用户中心调整;空/None = 不限)
        default_level = _get_setting('default_allowed_levels', '8') or None
        default_limit_raw = _get_setting('default_download_limit', '1')
        try:
            default_limit = int(default_limit_raw) if default_limit_raw else None
        except (TypeError, ValueError):
            default_limit = None  # 设置异常时按不限处理
        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            email=email,
            allowed_levels=default_level,
            download_limit=default_limit,
        )
        db.session.add(user)
        db.session.commit()

        # 注册成功不自动登录:不签发 token,用户需自行登录
        return jsonify({'username': user.username, 'email': user.email})

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
        info = user.to_dict()
        # 附带已用限额,前端展示"已下载 x / 上限 y"
        info['download_used'] = len(_user_download_used(user.id))
        return jsonify(info)

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
        user = current_user()
        data = request.get_json()
        ids = _normalize_ids(data)
        if ids is None:
            return jsonify({'error': '缺少 ids 参数'}), 400
        if not ids:
            return jsonify({'error': 'ids 不能为空'}), 400
        if len(ids) > app.config['MAX_BATCH_DOWNLOADS']:
            return jsonify({
                'error': f'单次最多下载 {app.config["MAX_BATCH_DOWNLOADS"]} 个流域'
            }), 400

        # 下载用途必填(每次下载都需要)
        reason = (data.get('reason') or '').strip()
        if not reason:
            return jsonify({'error': '请填写下载用途后再下载', 'error_type': 'reason_required'}), 400
        if len(reason) > 200:
            return jsonify({'error': '下载用途不能超过 200 字'}), 400

        # 科研单位必填(每次下载都需要;空值兜底链在申请放行路径解析后执行)
        institution = (data.get('institution') or '').strip()
        if len(institution) > 100:
            return jsonify({'error': '科研单位不能超过 100 字'}), 400

        existing_ids = [w.id for w in Watershed.query.filter(Watershed.id.in_(ids)).all()]
        invalid_ids = [i for i in ids if i not in existing_ids]
        if invalid_ids:
            return jsonify({'error': f'以下编号不存在: {invalid_ids}'}), 404

        # 管理员默认不受限(不限额、不限级别);非管理员走申请放行路径:
        # application_id 对应的已批准申请须覆盖本次全部编号,豁免限额/级别校验,放行后标记为已用,不可重复使用
        exempt = bool(user.is_admin)
        approved_app = None
        application_id = data.get('application_id')
        if application_id:
            approved_app = DownloadApplication.query.filter_by(id=application_id, user_id=user.id).first()
            if not approved_app or approved_app.status != 'approved':
                return jsonify({'error': '申请不存在或尚未通过审批'}), 403
            if not set(ids).issubset({w.strip() for w in (approved_app.watershed_ids or '').split(',') if w.strip()}):
                return jsonify({'error': '申请批准的范围与本次下载不一致'}), 403
            exempt = True

        # 科研单位兜底链:申请快照 → 用户资料 → 400(兼容旧申请/老用户无单位数据)
        if not institution:
            if approved_app and (approved_app.institution or '').strip():
                institution = approved_app.institution.strip()
            elif (user.institution or '').strip():
                institution = user.institution.strip()
            else:
                return jsonify({'error': '请填写科研单位', 'error_type': 'institution_required'}), 400

        if not exempt:
            # 级别限制:用户可下载级别集合(空 = 不限)
            allowed_levels = _parse_allowed_levels(user)
            if allowed_levels:
                restricted = [
                    w.id for w in Watershed.query.filter(Watershed.id.in_(ids)).all()
                    if w.level not in allowed_levels
                ]
                if restricted:
                    return jsonify({
                        'error': f'您的下载权限仅限 {sorted(allowed_levels)} 级流域，编号 {restricted} 超出可下载级别。如有需要可提交申请',
                        'error_type': 'level_restricted',
                        'restricted_ids': restricted,
                    }), 403
            # 数量限额:累计已下载流域个数(download_limit=None 表示不限)
            if user.download_limit is not None:
                used = _user_download_used(user.id)
                new_ids = [i for i in ids if i not in used]
                if len(used) + len(new_ids) > user.download_limit:
                    return jsonify({
                        'error': f'您已下载 {len(used)} 个流域，可下载上限 {user.download_limit} 个，本次需新增 {len(new_ids)} 个已超出限额。如有需要可提交申请',
                        'error_type': 'quota_exceeded',
                        'used': len(used),
                        'limit': user.download_limit,
                        'new_ids': new_ids,
                    }), 403

        try:
            zip_path = run_clip(ids, Path(app.config['JOB_ROOT']))
        except Exception:
            app.logger.exception('裁剪或打包失败，流域编号: %s', ids)
            return jsonify({'error': '裁剪或打包失败，请联系管理员查看服务日志'}), 500

        # 下载成功:写入审计日志(谁/何时/下载了什么/用途/科研单位/多大),并记录用户最近一次单位用于弹窗预填
        try:
            db.session.add(DownloadLog(
                user_id=user.id,
                username=user.username,
                watershed_ids=','.join(ids),
                reason=reason,
                institution=institution,
                file_size=os.path.getsize(zip_path),
            ))
            # 申请放行下载:标记为已用(一次性),用户中心不可再重复下载
            if approved_app:
                approved_app.status = 'used'
            user.institution = institution
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f'[audit] 下载日志写入失败: {e}')

        # 下载文件名: CONCN_datahub_<流域编号>_<下载日期>.zip(多流域编号用 _ 连接;磁盘文件仍用任务名,避免冲突)
        download_name = f"CONCN_datahub_{'_'.join(ids)}_{datetime.now().strftime('%Y%m%d')}.zip"
        return send_file(zip_path, as_attachment=True, download_name=download_name)

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

    # ---------- 下载申请与站内通知 ----------
    @app.route('/api/applications', methods=['POST'])
    @login_required
    def create_application():
        """提交下载申请:超限/级别受限时,说明用途申请放行指定流域。"""
        user = current_user()
        data = request.get_json(silent=True) or {}
        ids = _normalize_ids(data)
        if ids is None or not ids:
            return jsonify({'error': '请选择要申请的流域'}), 400
        if len(ids) > app.config['MAX_BATCH_DOWNLOADS']:
            return jsonify({'error': f'单次最多申请 {app.config["MAX_BATCH_DOWNLOADS"]} 个流域'}), 400

        reason = (data.get('reason') or '').strip()
        if not reason:
            return jsonify({'error': '请填写申请理由/用途'}), 400
        if len(reason) > 200:
            return jsonify({'error': '申请理由不能超过 200 字'}), 400

        # 科研单位必填(申请时校验;无兜底,老数据不含单位)
        institution = (data.get('institution') or '').strip()
        if not institution:
            return jsonify({'error': '请填写科研单位', 'error_type': 'institution_required'}), 400
        if len(institution) > 100:
            return jsonify({'error': '科研单位不能超过 100 字'}), 400

        existing_ids = [w.id for w in Watershed.query.filter(Watershed.id.in_(ids)).all()]
        invalid_ids = [i for i in ids if i not in existing_ids]
        if invalid_ids:
            return jsonify({'error': f'以下编号不存在: {invalid_ids}'}), 404

        # 同一用户已有待审批且流域集合相同的申请:拦截重复提交
        pending = DownloadApplication.query.filter_by(user_id=user.id, status='pending').all()
        for app_rec in pending:
            if set((app_rec.watershed_ids or '').split(',')) == set(ids):
                return jsonify({'error': '您已提交过相同流域的申请，请等待管理员审批'}), 409

        db.session.add(DownloadApplication(
            user_id=user.id,
            username=user.username,
            watershed_ids=','.join(ids),
            reason=reason,
            institution=institution,
            status='pending',
        ))
        # 记录用户最近一次单位,下次下载/申请弹窗自动预填
        user.institution = institution
        db.session.commit()
        return jsonify({'ok': True, 'message': '申请已提交，请等待管理员审批，审批结果将在用户中心通知您'})

    @app.route('/api/applications/mine', methods=['GET'])
    @login_required
    def my_applications():
        """当前用户的申请列表(最近优先)"""
        user = current_user()
        items = (
            DownloadApplication.query.filter_by(user_id=user.id)
            .order_by(DownloadApplication.created_at.desc(), DownloadApplication.id.desc())
            .all()
        )
        return jsonify([a.to_dict() for a in items])

    @app.route('/api/notifications', methods=['GET'])
    @login_required
    def notifications():
        """当前用户的通知列表(最近 30 条) + 未读数"""
        user = current_user()
        items = (
            Notification.query.filter_by(user_id=user.id)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(30)
            .all()
        )
        unread = Notification.query.filter_by(user_id=user.id, is_read=False).count()
        return jsonify({'unread': unread, 'items': [n.to_dict() for n in items]})

    @app.route('/api/notifications/read', methods=['POST'])
    @login_required
    def notifications_read():
        """全部标为已读"""
        user = current_user()
        Notification.query.filter_by(user_id=user.id, is_read=False).update({'is_read': True})
        db.session.commit()
        return jsonify({'ok': True})

    # ---------- 管理员 API ----------
    @app.route('/api/admin/users', methods=['GET'])
    @admin_required
    def admin_users():
        """用户列表:含角色、限额、级别、已用数量"""
        users = User.query.order_by(User.id.asc()).all()
        result = []
        for u in users:
            d = u.to_dict()
            d['id'] = u.id
            d['download_used'] = len(_user_download_used(u.id))
            result.append(d)
        return jsonify(result)

    @app.route('/api/admin/users/<int:user_id>', methods=['PUT'])
    @admin_required
    def admin_update_user(user_id):
        """设置用户下载限额/允许级别/是否管理员(download_limit=None 或 allowed_levels 为空 = 不限)。
        是否管理员(是/否)仅最高管理员可改;最高管理员本人不可被降级。"""
        admin = current_user()
        target = User.query.get(user_id)
        if not target:
            return jsonify({'error': '用户不存在'}), 404
        data = request.get_json(silent=True) or {}

        # 最高管理员仅最高管理员本人可管理;其管理员状态不可被任何人取消
        if target.is_super_admin and not admin.is_super_admin:
            return jsonify({'error': '无权修改最高管理员'}), 403
        if target.is_super_admin and 'is_admin' in data and data['is_admin'] is False:
            return jsonify({'error': '不能取消最高管理员的管理员权限'}), 400
        # 设置/取消管理员仅限最高管理员
        if 'is_admin' in data and not admin.is_super_admin:
            return jsonify({'error': '仅最高管理员可设置管理员'}), 403

        if 'download_limit' in data:
            v = data['download_limit']
            if v is None or v == '':
                target.download_limit = None  # 不限
            else:
                try:
                    v = int(v)
                except (TypeError, ValueError):
                    return jsonify({'error': '下载限额需为整数'}), 400
                if v < 0:
                    return jsonify({'error': '下载限额不能为负数'}), 400
                target.download_limit = v

        if 'allowed_levels' in data:
            raw = (data.get('allowed_levels') or '').strip()
            if not raw or raw == '不限':
                target.allowed_levels = None
            else:
                levels = []
                for part in raw.split(','):
                    part = part.strip()
                    if not part.isdigit() or int(part) not in {2, 4, 6, 8, 10, 12, 14}:
                        return jsonify({'error': '允许级别需为 2~14 的偶数级别，多个用逗号分隔'}), 400
                    levels.append(part)
                target.allowed_levels = ','.join(dict.fromkeys(levels))

        if 'is_admin' in data and isinstance(data['is_admin'], bool):
            if target.id == admin.id and not data['is_admin']:
                return jsonify({'error': '不能取消自己的管理员权限'}), 400
            target.is_admin = data['is_admin']
            if data['is_admin']:
                # 管理员默认不受限:不限额、不限级别
                target.download_limit = None
                target.allowed_levels = None

        db.session.commit()
        return jsonify({'ok': True})

    @app.route('/api/admin/default-settings', methods=['GET'])
    @admin_required
    def admin_get_default_settings():
        """当前默认下载级别/数量(新注册用户生效;空字符串 = 不限)。"""
        return jsonify({
            'allowed_levels': _get_setting('default_allowed_levels', '8') or '',
            'download_limit': _get_setting('default_download_limit', '1') or '',
        })

    @app.route('/api/admin/default-settings', methods=['POST'])
    @admin_required
    def admin_set_default_settings():
        """调整默认下载级别/数量:
        保存为新注册用户的默认值,并把仍等于旧默认值的普通用户一并更新;
        已被单独调整过权限(值不同于旧默认)的用户不受影响。"""
        data = request.get_json(silent=True) or {}
        # 旧默认值:设置尚未保存过(首次部署)时,以旧硬编码默认 '2'/'1' 为基准,
        # 让首批存量用户(注册时落在列默认值上)在第一次保存时一并迁移到新默认
        old_level = _get_setting('default_allowed_levels', '2') or None
        old_limit_raw = _get_setting('default_download_limit', '1')
        try:
            old_limit = int(old_limit_raw) if old_limit_raw else None
        except (TypeError, ValueError):
            old_limit = None

        # 校验并保存新默认级别
        raw_level = (data.get('allowed_levels') or '').strip()
        if not raw_level or raw_level == '不限':
            new_level = None
        else:
            levels = []
            for part in raw_level.split(','):
                part = part.strip()
                if not part.isdigit() or int(part) not in {2, 4, 6, 8, 10, 12, 14}:
                    return jsonify({'error': '允许级别需为 2~14 的偶数级别，多个用逗号分隔'}), 400
                levels.append(part)
            new_level = ','.join(dict.fromkeys(levels))

        # 校验并保存新默认数量
        raw_limit = data.get('download_limit')
        if raw_limit is None or raw_limit == '':
            new_limit = None
        else:
            try:
                new_limit = int(raw_limit)
            except (TypeError, ValueError):
                return jsonify({'error': '下载限额需为整数'}), 400
            if new_limit < 0:
                return jsonify({'error': '下载限额不能为负数'}), 400

        _set_setting('default_allowed_levels', new_level or '')
        _set_setting('default_download_limit', str(new_limit) if new_limit is not None else '')

        # 存量普通用户:仍等于旧默认值的批量更新(SQLAlchemy == None 会生成 IS NULL)
        updated_levels = updated_limits = 0
        if old_level != new_level:
            updated_levels = User.query.filter(
                User.is_admin.is_(False), User.allowed_levels == old_level
            ).update({'allowed_levels': new_level}, synchronize_session=False)
        if old_limit != new_limit:
            updated_limits = User.query.filter(
                User.is_admin.is_(False), User.download_limit == old_limit
            ).update({'download_limit': new_limit}, synchronize_session=False)

        db.session.commit()
        return jsonify({'ok': True, 'updated_levels': updated_levels, 'updated_limits': updated_limits})

    @app.route('/api/admin/downloads', methods=['GET'])
    @admin_required
    def admin_downloads():
        """全部用户的下载记录(含用途),分页"""
        try:
            page = max(1, request.args.get('page', type=int) or 1)
            page_size = request.args.get('page_size', type=int) or 50
        except ValueError:
            page, page_size = 1, 50
        page_size = max(1, min(page_size, 200))
        query = DownloadLog.query.order_by(DownloadLog.created_at.desc(), DownloadLog.id.desc())
        total = query.count()
        logs = query.offset((page - 1) * page_size).limit(page_size).all()
        return jsonify({
            'total': total,
            'page': page,
            'page_size': page_size,
            'items': [log.to_dict() for log in logs],
        })

    @app.route('/api/admin/applications', methods=['GET'])
    @admin_required
    def admin_applications():
        """全部下载申请,可按状态过滤(默认全部,最近优先)"""
        status = request.args.get('status', '').strip()
        query = DownloadApplication.query
        if status:
            query = query.filter_by(status=status)
        items = (
            query.order_by(DownloadApplication.created_at.desc(), DownloadApplication.id.desc())
            .all()
        )
        return jsonify([a.to_dict() for a in items])

    def _handle_application(app_id, status):
        """审批申请:置状态 + 留备注 + 给用户发站内通知"""
        app_rec = DownloadApplication.query.get(app_id)
        if not app_rec:
            return jsonify({'error': '申请不存在'}), 404
        if app_rec.status != 'pending':
            return jsonify({'error': '该申请已处理，请刷新列表'}), 400

        data = request.get_json(silent=True) or {}
        comment = (data.get('comment') or '').strip()
        app_rec.status = status
        app_rec.admin_comment = comment or None
        app_rec.processed_at = datetime.utcnow()
        if status == 'approved':
            content = f'您的下载申请 #{app_rec.id} 已通过审批，请在用户中心「我的申请」中下载数据'
        else:
            content = f'您的下载申请 #{app_rec.id} 未通过审批' + (f'：{comment}' if comment else '')
        db.session.add(Notification(user_id=app_rec.user_id, content=content))
        db.session.commit()
        return jsonify({'ok': True})

    @app.route('/api/admin/applications/<int:app_id>/approve', methods=['POST'])
    @admin_required
    def admin_approve_application(app_id):
        return _handle_application(app_id, 'approved')

    @app.route('/api/admin/applications/<int:app_id>/reject', methods=['POST'])
    @admin_required
    def admin_reject_application(app_id):
        return _handle_application(app_id, 'rejected')

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
