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

    def to_dict(self):
        return {
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'watershed_ids': self.watershed_ids.split(',') if self.watershed_ids else [],
            'count': len(self.watershed_ids.split(',')) if self.watershed_ids else 0,
            'file_size': self.file_size,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }