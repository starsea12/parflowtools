from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Watershed(db.Model):
    __tablename__ = 'watersheds'

    id = db.Column(db.String(14), primary_key=True)  # 14位数字编码
    name = db.Column(db.String(100), nullable=False)  # 保留但前端不显示
    region = db.Column(db.String(50), nullable=False)
    level = db.Column(db.Integer, nullable=False)    # 2,4,6,...14
    lng = db.Column(db.Float, nullable=True)
    lat = db.Column(db.Float, nullable=True)
    area = db.Column(db.Float, nullable=True)        # 新增面积（单位：km²）
    description = db.Column(db.Text, nullable=True)  # 保留但前端不显示

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'region': self.region,
            'level': self.level,
            'lng': self.lng,
            'lat': self.lat,
            'area': self.area,
            'description': self.description
        }


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(16), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    failed_attempts = db.Column(db.Integer, default=0, nullable=False)   # 连续登录失败次数
    locked_until = db.Column(db.DateTime, nullable=True)                 # 锁定截止时间(超过则解禁)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)      # 是否管理员
    is_super_admin = db.Column(db.Boolean, default=False, nullable=False)  # 是否最高管理员(仅其可设置/取消管理员)
    download_limit = db.Column(db.Integer, nullable=True, default=1)     # 可下载流域个数上限(None=不限)
    allowed_levels = db.Column(db.String(50), nullable=True, default='8')  # 可下载流域级别,逗号分隔(None/空=不限)
    institution = db.Column(db.String(100), nullable=True)                 # 科研单位(最近一次填写,下载/申请时更新,用于弹窗预填)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'is_admin': bool(self.is_admin),
            'is_super_admin': bool(self.is_super_admin),
            'download_limit': self.download_limit,
            'allowed_levels': self.allowed_levels,
            'institution': self.institution or '',
        }


class AuthToken(db.Model):
    __tablename__ = 'auth_tokens'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)  # 过期时间,签发时设置


class PasswordResetToken(db.Model):
    """忘记密码重置码:一个用户同一时间只有一条(重新申请覆盖旧的),过期即失效。"""
    __tablename__ = 'password_reset_tokens'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    code = db.Column(db.String(16), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)  # 过期时间,签发时设置
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DownloadLog(db.Model):
    __tablename__ = 'download_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    username = db.Column(db.String(16), nullable=False)  # 冗余存用户名,展示免联表
    watershed_ids = db.Column(db.Text, nullable=False)   # 逗号分隔的流域 id
    file_size = db.Column(db.Integer, nullable=False)    # zip 字节数
    reason = db.Column(db.Text, nullable=True)           # 下载用途(每次下载必填)
    institution = db.Column(db.String(100), nullable=True)  # 科研单位快照(下载时必填)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'watershed_ids': self.watershed_ids.split(',') if self.watershed_ids else [],
            'count': len(self.watershed_ids.split(',')) if self.watershed_ids else 0,
            'file_size': self.file_size,
            'reason': self.reason,
            'institution': self.institution or '',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }


class DownloadApplication(db.Model):
    """下载申请:用户超限或级别受限时提交,管理员审批通过后一次性放行申请覆盖的流域。"""
    __tablename__ = 'download_applications'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    username = db.Column(db.String(16), nullable=False)   # 冗余存用户名,展示免联表
    watershed_ids = db.Column(db.Text, nullable=False)    # 逗号分隔的流域 id
    reason = db.Column(db.Text, nullable=False)           # 申请理由/用途
    institution = db.Column(db.String(100), nullable=True)  # 科研单位快照(申请时必填,老数据为 NULL)
    status = db.Column(db.String(10), nullable=False, default='pending', index=True)  # pending/approved/rejected/used
    admin_comment = db.Column(db.Text, nullable=True)     # 管理员批复备注
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    processed_at = db.Column(db.DateTime, nullable=True)  # 管理员处理时间

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'watershed_ids': self.watershed_ids.split(',') if self.watershed_ids else [],
            'count': len(self.watershed_ids.split(',')) if self.watershed_ids else 0,
            'reason': self.reason,
            'institution': self.institution or '',
            'status': self.status,
            'admin_comment': self.admin_comment,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'processed_at': self.processed_at.strftime('%Y-%m-%d %H:%M:%S') if self.processed_at else None,
        }


class Notification(db.Model):
    """站内通知:管理员审批申请后给用户发一条,用户中心展示(未读角标)。"""
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'is_read': bool(self.is_read),
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
        }


class SiteSetting(db.Model):
    """系统级设置(键值对):新注册用户的默认下载级别/数量等。
    value 统一存字符串;空字符串 = 不限。"""
    __tablename__ = 'site_settings'

    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(200), nullable=True)