import os
import zipfile
from pathlib import Path
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from config import Config
from models import db, Watershed
from clip_worker import run_clip

def create_app():
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)
    app.config['JSON_AS_ASCII'] = False

    Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    CORS(app)

    # ---------- API 路由 ----------
    @app.route('/api/watersheds', methods=['GET'])
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
    def get_watershed(id):
        watershed = Watershed.query.get(id)
        if not watershed:
            return jsonify({'error': '流域不存在'}), 404
        return jsonify(watershed.to_dict())

    @app.route('/api/download', methods=['POST'])
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

        ids = [i for i in ids if i.strip()]
        if not ids:
            return jsonify({'error': 'ids 不能为空'}), 400

        existing_ids = [w.id for w in Watershed.query.filter(Watershed.id.in_(ids)).all()]
        invalid_ids = [i for i in ids if i not in existing_ids]
        if invalid_ids:
            return jsonify({'error': f'以下编号不存在: {invalid_ids}'}), 404

        try:
            zip_path = run_clip(ids, Path(app.config['UPLOAD_FOLDER']))
            return send_file(zip_path, as_attachment=True)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'裁剪或打包失败: {str(e)}'}), 500

    # ---------- 前端静态文件服务 ----------
    # 修正为你的实际路径
    DIST_DIR = '/data/wangzihan-data/parflow-website/dist'

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        # 如果是 API 请求，不处理（API 路由优先）
        if path.startswith('api/'):
            return '', 404

        # 尝试返回静态文件
        full_path = os.path.join(DIST_DIR, path)
        if path != '' and os.path.exists(full_path) and os.path.isfile(full_path):
            return send_from_directory(DIST_DIR, path)
        else:
            # 返回 index.html（支持 Vue Router）
            return send_from_directory(DIST_DIR, 'index.html')

    return app


# ---------- 创建应用实例（供 gunicorn 使用） ----------
app = create_app()

# ---------- 初始化数据库（首次运行） ----------
with app.app_context():
    db.create_all()
    if Watershed.query.count() == 0:
        sample_data = [
            Watershed(
                id='01010105000000',
                name='长江上游',
                region='长江流域',
                level=2,
                lng=102.2,
                lat=28.5,
                description='位于青藏高原至宜昌段，水资源丰富。'
            ),
            Watershed(
                id='01010106000000',
                name='黄河中游',
                region='黄河流域',
                level=4,
                lng=110.3,
                lat=37.6,
                description='流经黄土高原，泥沙含量大。'
            ),
            Watershed(
                id='01010107000000',
                name='淮河干流',
                region='淮河流域',
                level=6,
                lng=117.1,
                lat=33.2,
                description='介于长江与黄河之间，是重要的农业区。'
            ),
        ]
        db.session.bulk_save_objects(sample_data)
        db.session.commit()
        print("示例数据已插入数据库。")

# ---------- 直接运行（开发/测试） ----------
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=50001)