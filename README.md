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

## 自然语言景点检索（规则版 MVP）

左下角「一句话找景点」支持「附近5公里的博物馆」「南京历史文化景点」等有限规则。解析分类与半径后，查询现有 PostGIS 数据，并在地图显示结果。

- 这是规则检索，尚未接入 GPT 或其他大模型，不声称具备真正的 AI 行程规划。
- 「附近」指地图中心位置而不是 GPS 实时位置；默认半径5公里。
- 预算、少走路、行程、开放时间等未实现的条件会明确说明没有参与检索。
- 景点范围只覆盖项目已收录 POI（当前40条）；路线连线并非道路导航。
- 此功能不需要密钥，也不把输入传给第三方模型。

验证：在项目根目录运行以下命令：

    .\.venv\Scripts\python.exe -m unittest discover -s tests -p test_natural_language.py
    .\.venv\Scripts\python.exe tests/verify_api.py
    node tests/frontend-workflow.mjs
    cd frontend
    npm run build

后面的 API 验证需要本地数据库和后端处于运行状态。

## 景点顺序预览（开发分支）

新增可折叠的「景点顺序预览（直线距离）」面板，输入可选的景点分类需求、选择2～6个站点，后端先用已有PostGIS记录过滤候选，然后采用就近贪心策略排序，并通过现有路线面板展示。所有数字是地理直线距离估算；**不提供真实路网/导航、行程用时、开放时间校验或全局最优保证**。地图中心为起点，不是GPS。

需要在本地同时运行数据库、后端、前端，执行下面的回归检查（新提交尚未在Windows本机执行）：

    .\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
    .\.venv\Scripts\python.exe tests/verify_api.py
    node tests/frontend-workflow.mjs
    cd frontend
    npm run build

最后在网页展开预览面板，生成3站历史文化景点顺序并检查地图连线。确认无误后再考虑合并；不要把此版本描述成GPT/AI自动行程规划。


## 第三阶段：POI 旅游语义卡片（PR #3，待本机验收）

`GET /api/tourism/places/{id}` 现在由 FastAPI 正式注册，查询 PostgreSQL 的真实 POI 信息，
缺失 ID 返回 HTTP 404。扩展列不存在时仍可读取基本属性并显示“暂无数据”，而不是编造信息。
点击地图点位或搜索结果，会向后端请求旅游卡片；请求过程中显示加载状态，
连续切换景点时取消过时请求。原有搜索、收藏、路线预览 API 保留。

`data/poi_tourism_metadata.json` 是与 `data/nanjing_pois.csv` 完全匹配的40条旅游属性草稿。
**游览时长只是人工规划估算，非景区官方信息**；室内外不明确的场景用 `null`，
尚未核实的推荐时段用空字符串。绝不把估算值展示为真实开放时间、票价或实时客流。
前端因此删除了之前硬编码的“开放时间”和“推荐指数”演示数据。

### 本地应用流程（PowerShell）

> 在执行 `--apply` 之前，确认 `backend/.env` 指向项目的本地测试数据库，并根据需要备份。
> 该操作会更新现有40个 POI 的旅游字段，虽然保留几何数据和基础属性，但不能自动恢复旧旅游字段。

从项目根目录依次执行：

```powershell
cd D:\smart-tourism
git fetch origin
git switch feat/poi-tourism-metadata-20261008
git pull --ff-only

# 第一步：纯文件校验，不修改数据库
.\.venv\Scripts\python.exe scripts/import_tourism_metadata.py

# 第二步：显式执行幂等表结构迁移与40行旅游元数据更新
.\.venv\Scripts\python.exe scripts/import_tourism_metadata.py --apply

# 第三步：单元测试（无需启动服务器）
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"

# 第四步：启动数据库及后端后执行 API/数据库测试
.\.venv\Scripts\python.exe tests/verify_database.py
.\.venv\Scripts\python.exe tests/verify_api.py

# 第五步：前端回归与生产构建
node tests/frontend-workflow.mjs
cd frontend
npm run build
```

`--apply` 会先核对数据库内40个名称与 CSV 是否完全匹配。
如缺少景点、存在重名或数量不等于40，脚本会拒绝更新并回滚。
迁移和40行 UPDATE 在一个事务中提交；重复运行不会重复插入记录。
数据库原有的 `id`、`geom`、`category`、`rating` 等字段不变。

浏览器验收：访问 `http://localhost:5173`，分别点击“南京博物院”和“夫子庙”，
确认景点详情可以显示建议停留时间、兴趣标签、游览环境、资料尚未核实的说明；
连续切换两个景点不应显示上一景点的详情。确认不存在景点返回404。
PR 维持 Draft，直到这些检查在 Windows 本机通过。
