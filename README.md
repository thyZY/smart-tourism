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


## 第四阶段：DeepSeek 辅助检索与候选行程（Draft / 本地验收中）

已新增 `POST /api/ai/tourism-search`（`GET /api/places/natural` 规则版保留）。
前端左下角“一句话找景点”现调用新接口，真实 POI 只从 PostGIS 取出，
并可把候选站点显示为**直线距离**预览路线（不保证少走路、可达性、
营业时间、交通时间或适合一天的实际日程）。

- **没有 DeepSeek Key**：自动使用本地规则解析，`mode=rule_based`，不会联网请求模型。
- **有 DeepSeek Key**：调用 DeepSeek JSON 意图解析，成功时 `mode=deepseek`；
  请求失败或输出不合法时返回 `mode=rule_based_fallback` 并继续使用本地数据。
- 模型只解析限定的 POI 类别、避开类别、时间/步行偏好和附近半径；
  不允许大模型创建 POI、写 SQL、指定未入库景点或声称真实导航。
- 模型/规则解析的停留天数和少走路偏好暂不进入真实路网优化，
  会在 `unsupported` 中显式提醒。
- 外部模型会接收用户输入的旅游需求文本；不要输入隐私或敏感信息。

### 本地可选启用 DeepSeek（请勿发送/提交 Key）

编辑**本地** `backend/.env`，保留既有 DB 配置，在末尾添加：

```dotenv
DEEPSEEK_API_KEY=你的私有API密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

根目录 `.gitignore` 已排除 `.env`。不要把 Key 放在前端的
`VITE_*` 变量、截图、GitHub PR、代码、聊天或日志中；配置后重启后端。
若实际模型名称不同，按 DeepSeek 官方控制台可用模型修改 `DEEPSEEK_MODEL`。
未配置 Key 完全可以先做无 Key 回归测试。

在两个终端运行数据库/后端与前端，第三个 PowerShell 终端执行：

```powershell
cd D:\smart-tourism
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
node tests/frontend-workflow.mjs
cd frontend
npm run build
```

手动 API 测试（后端必须已启动）：

```powershell
$body = @{query="南京一天历史文化景点，少走路";lng=118.7921;lat=32.0407;max_stops=3} | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8010/api/ai/tourism-search" -Method Post -ContentType "application/json; charset=utf-8" -Body ([Text.Encoding]::UTF8.GetBytes($body))
```

检查返回的 `mode`、`intent`、`places.features` 和
`itinerary_preview.stops`。无 Key 时 `mode` 必须为 `rule_based`；
浏览器在“查找”后应出现对应真实地图点位，并可点击显示路线预览。
所有源字段、坐标都应可追溯至当前 PostGIS 的 `places` 表。

## 第五阶段：道路路网寻路 MVP（仅两站步行）

已增加 `POST /api/routing/route`，由数据库中真实的两个景点 ID 查询 WGS84 坐标，
再通过 Valhalla 基于 OpenStreetMap 路网计算步行道路折线、距离和预计耗时。
地图仍保持原有蓝色直线预览；在「我的路线」面板**恰好选择两个景点**后，
可以点击「计算真实道路步行路线」，成功后改为绿色道路折线并展示时长。
增删景点会立即清除旧道路结果，避免错误沿用。
寻路失败会显示明确错误并保留蓝色直线预览；三站以上目前仍然使用直线预览。

### 路由服务及环境变量

默认开发验证服务为公共演示节点 `https://valhalla1.openstreetmap.de/route`。
该节点不提供稳定性或服务等级保证，仅用于少量实验验证，不能直接作为
生产环境正式依赖。可在本地 `backend/.env` 覆盖（不要把密钥或个人配置入库）：

```dotenv
VALHALLA_ROUTE_URL=https://valhalla1.openstreetmap.de/route
```

后续自建 Valhalla 可将其改为受信任的自有服务 URL。
接口只支持 `mode=pedestrian`，不需要 DeepSeek Key。
外部路由服务只收到两个 POI 坐标，不收到用户聊天文字或数据库账号。
Valhalla 使用的 encoded polyline 为**六位小数精度**；代码转换为
GeoJSON 的 `[longitude, latitude]` 顺序供 MapLibre 使用。

### 本地更新和验收

```powershell
cd D:\smart-tourism
git fetch origin
git switch feat/poi-tourism-metadata-20261008
git pull --ff-only

.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_road_routing.py"
node tests/frontend-workflow.mjs
cd frontend
npm run build
```

分别启动本地后端（端口8010）与前端（端口5173）后，打开
`http://localhost:5173`。在搜索列表选择“南京博物院”“南京总统府”
并分别加入「我的路线」，然后点击「计算真实道路步行路线」；
期望能看到绿色道路折线、道路距离和预计步行时间。用户已在本机用相同两个
数据库 POI 坐标通过公开 Valhalla 实测成功（当次返回0.908km / 11.3分钟），
但公共地图数据与路线服务可能更新，**不要把该数值写死在自动化测试中**。

还可从 PowerShell 调用后端接口（请按数据库内实际 ID 修改）：

```powershell
$pois = (Invoke-RestMethod "http://127.0.0.1:8010/api/places").features
$a = $pois | Where-Object { $_.properties.name -eq "南京博物院" } | Select-Object -First 1
$b = $pois | Where-Object { $_.properties.name -eq "南京总统府" } | Select-Object -First 1
$body = @{from_id=$a.properties.id;to_id=$b.properties.id;mode="pedestrian"} | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8010/api/routing/route" -Method Post -ContentType "application/json" -Body $body
```

已新增单元测试使用模拟外部 HTTP 响应，不需要 API Key 或公网服务；
但真实公网端点、Windows 前端构建仍需本机执行和验收。
此路线提供的是基于 OSM 的**非实时步行估算**，尚无入口点校正、
道路无障碍/坡度筛选、多站道路距离矩阵，也不能视为实时导航。
