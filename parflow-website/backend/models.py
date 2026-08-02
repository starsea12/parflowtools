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