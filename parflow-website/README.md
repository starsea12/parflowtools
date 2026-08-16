# CONCN DataHub 网站

Vue 3 前端和 Flask 后端，共用仓库根目录的 `concnshare` 裁剪包。

## 前端开发

需要 Node.js 22.18+：

```bash
npm install
npm run dev
```

开发服务器会将 `/api` 代理到 `http://localhost:50001`。

## 后端开发

先在仓库根目录创建并激活 `concnshare` Conda 环境，然后运行：

```bash
cd parflow-website/backend
pip install -r requirements.txt
python app.py
```

首次启动会自动创建：

- `backend/instance/watershed.db`
- `backend/boundary_cache/`
- `backend/jobs/`

每个下载请求会在 `jobs/<job_id>/` 中保存独立的状态、输出和 ZIP，不会与其他请求共用结果目录。

## 导入流域信息

导入前会先完整校验文件，并默认备份当前 SQLite 数据库。只有显式传入 `--replace` 才会替换现有记录：

```bash
python import_excel.py /path/to/watershed_info.xlsx --replace
python import_csv.py /path/to/watershed_info.csv --replace
```

## 环境变量

集群路径都有当前服务器默认值，通常无需设置：

- `CONCN_SHP_DIR`
- `CONCN_TIF_DIR`
- `CONCN_INPUT_PFB_DIR`
- `PARFLOW_PFMASK_CMD`
- `CONCN_DATA_VERSION`，默认 `1.1`
- `CONCN_DIST_DIR`
- `CONCN_JOB_ROOT`
- `CONCN_MAX_BATCH_DOWNLOADS`，默认 `10`
- `CONCN_ALLOWED_ORIGINS`，多个来源用逗号分隔，内测默认 `*`
- `FLASK_DEBUG`，仅开发调试时设置为 `1`
