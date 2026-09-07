# Smart Tourism WebGIS

Vue 3 / Vite / MapLibre GL + FastAPI + PostgreSQL / PostGIS。

## 本地启动（Windows PowerShell）

先启动 PostgreSQL 服务。后端使用项目现有 `.venv`，`backend/.env` 配置
`DB_HOST`、`DB_PORT`、`DB_NAME=smart_tourism`、`DB_USER`、`DB_PASSWORD`。
请勿提交 `.env` 或密码。

在项目根目录的两个终端分别执行（Ctrl+C 停止）：

```powershell
cd D:\smart-tourism
.\start-backend.ps1
```

```powershell
cd D:\smart-tourism
.\start-frontend.ps1
```

如果本机执行策略阻止脚本，可只为本次进程执行
`powershell -NoProfile -ExecutionPolicy Bypass -File .\start-backend.ps1`
（前端同理），不需要永久修改系统策略。

前端：http://localhost:5173；后端：http://127.0.0.1:8010。
首次安装前端依赖：在 `frontend` 下执行 `npm ci`。
前端脚本固定 5173；端口占用会报错，避免自动切到未配置 CORS 的端口。

## 新数据库初始化

安装含 PostGIS 的 PostgreSQL，并确保 `psql`、`createdb` 在 PATH 中。
以下以本机 `postgres` 角色为例，按本机配置替换用户和端口：

```powershell
createdb -h localhost -U postgres -E UTF8 smart_tourism
psql -h localhost -U postgres -d smart_tourism -v ON_ERROR_STOP=1 -f database/schema.sql
psql -h localhost -U postgres -d smart_tourism -v ON_ERROR_STOP=1 -f database/seed.sql
```

SQL 文件保持 UTF-8，保留 `\encoding UTF8`；用 `psql -f` 执行，避免
Windows 管道转码。先 schema 再 seed，重复串行执行不会新增重复 Demo 景点。
seed 会更新三个同名 Demo 景点的属性和坐标，不适合并发执行。
schema 包含 Point(4326)、评分约束和 `idx_places_geom` GiST 索引。
现有 geometry 索引不等于 `geom::geography` 表达式索引；大数据量时再基于
EXPLAIN 评估 Nearby 查询索引，本次不改空间 SQL。

## 使用与验证

- 初次加载显示三个 Demo POI。
- 输入“博物”并 Enter：定位南京博物院并显示 Popup。
- 等定位结束后点击“附近 5km”：按当时地图中心查询，自动展示所有结果。
- 点击夫子庙：显示 `距离：1.57 km`；普通搜索 Popup 不显示距离。
- 输入“不存在”：清除红点与 Popup，提示未找到并返回南京概览。
- 清空输入并 Enter：恢复三个 POI 和概览。
- 请求期间禁用输入和按钮；连接失败显示提示，可再次查询重试。

```powershell
.\.venv\Scripts\python.exe tests/verify_api.py
.\.venv\Scripts\python.exe tests/verify_database.py
node tests/frontend-workflow.mjs
cd frontend
npm run build
```

数据库验证在事务内创建独立 schema，执行 schema/seed 两次后回滚；不会修改
现有 places 数据。需要当前数据库角色有 CREATE SCHEMA 权限，且已安装 PostGIS。
