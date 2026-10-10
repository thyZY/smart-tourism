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


## 第六阶段：步行 / 骑行 / 驾车路网对比（Draft）

`POST /api/routing/route` 扩展至三种 Valhalla `costing` 模式：

| mode | 用户界面 | 地图道路折线 |
| --- | --- | --- |
| `pedestrian` | 🚶 步行 | 绿色 |
| `bicycle` | 🚲 骑行 | 橙色 |
| `auto` | 🚗 驾车 | 蓝色 |

不传 `mode` 仍按步行处理，保持已有 API 兼容。其他模式会得到 HTTP 422，
目前**不支持实时公交、地铁、出租车计价或实时路况**。引擎的距离和预计用时
为 OSM 路网模型估算；驾车不保证最新交通限制，骑行不保证每条道路可骑，
请勿将其当作现实导航或安全保证。公共 Valhalla 演示服务可能限流或无法覆盖某些道路。

操作：在「我的路线」中恰好选择两个景点，切换步行/骑行/驾车，
逐个点击「计算当前交通方式路线」。地图只显示当前选择模式的对应路线，
下方表格保留该次两景点组合已经算过的各模式距离与时间，
尚未计算显示「待计算」，**不会编造数值**。切回已计算方式直接使用前端缓存；
若增删景点则自动清除全部结果。道路失败时恢复虚线直线预览。

### Windows PowerShell 本地验收

```powershell
cd D:\smart-tourism
git fetch origin
git switch feat/poi-tourism-metadata-20261008
git pull --ff-only
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
node tests/frontend-workflow.mjs
cd frontend
npm run build
```

前后端重启后可用真实数据库的 POI ID 请求 `/api/routing/route`：

```powershell
$pois = (Invoke-RestMethod "http://127.0.0.1:8010/api/places").features
$a = $pois | Where-Object { $_.properties.name -eq "南京博物院" } | Select-Object -First 1
$b = $pois | Where-Object { $_.properties.name -eq "夫子庙" } | Select-Object -First 1
foreach ($mode in @("pedestrian", "bicycle", "auto")) {
  $body = @{from_id=$a.properties.id;to_id=$b.properties.id;mode=$mode} | ConvertTo-Json
  $result = Invoke-RestMethod -Uri "http://127.0.0.1:8010/api/routing/route" -Method Post -ContentType "application/json" -Body $body
  "$mode : $($result.properties.distance_km) km, $($result.properties.duration_minutes) minutes"
}
```

GitHub Actions 工作流 `.github/workflows/ci.yml` 在推送分支时执行 Python
离线测试、前端工作流和 Vite 构建。真正的公网寻路结果仍需 Windows 本地验证。


## 第七阶段：地图界面布局优化（Draft）

原版页面采用多个独立 absolute 浮窗，导致推荐主题、统计、交通路线和景点详情
在同一区域互相遮挡。本轮仅调整 Vue 结构、样式与默认折叠状态，**不改变
PostGIS 查询、DeepSeek 检索、Valhalla 路线或已收录 POI 业务逻辑**。

- **顶部工具栏**：景点搜索、附近、收藏、当前区域、地图显示模式；景点类别单行横向滚动，不再覆盖侧边栏。
- **左侧发现区**：滚动景点列表，底部顺序预览与 AI 辅助检索；地图缩放仍可使用。
- **右侧规划区**：路线比较占主要区域；推荐主题与统计默认折叠，展开时在栏内收缩或滚动，不压住路线。
- **景点详情**：宽屏位于右侧规划栏左方；窄屏改为可关闭的居中覆盖层。
- **窄屏布局（≤760px）**：左侧发现与下方路线规划分区独立滚动，防止挤压。
- 清理 Vite 默认的 1126px `#app` 宽度样式，设置 `zh-CN` 页面语言和应用标题。

### 验收

```powershell
cd D:\smart-tourism
git fetch origin
git switch feat/poi-tourism-metadata-20261008
git pull --ff-only
node tests/frontend-workflow.mjs
node tests/ui-layout.mjs
cd frontend
npm run build
```

运行前后端并打开 `http://localhost:5173`。
在默认页面确认右侧路线面板不再被“推荐主题”遮挡。
按顺序：选择南京博物院与夫子庙 → 切换并计算三种道路交通方式 →
展开/收起推荐主题和统计 → 打开/关闭景点详情 → 浏览搜索列表 →
调整浏览器宽度到约 900px 与 600px。验证路线数值和地图颜色不受布局影响；
窄屏区块应可滚动和关闭，不应出现完全不可点击的按钮。

注意：CI 里的 `tests/ui-layout.mjs` 是源码布局契约检测，不能替代真实浏览器视觉验收。
本轮仅完成静态前端布局优化，不包含拖拽面板或地图移动端手势新功能。


## 第八阶段：3—6 站道路时间矩阵与顺序优化（Draft / 待 Windows 实测）

已新增 `POST /api/routing/itinerary`，输入 3—6 个**不同且真实入库**的 POI ID
及 `mode=pedestrian|bicycle|auto`。第一站固定为出发景点，终点自由；
后端向 Valhalla `/sources_to_targets` 请求有向道路时间矩阵，
在最多6个景点内**精确枚举剩余站点排列**，选取矩阵总交通时间最短的顺序。
对于6站最多120种排列，规模适合离线计算。
随后独立请求一次 `/route` 获取优化顺序对应的**实际道路折线**（每段
Valhalla polyline6 解码），MapLibre 用当前交通模式颜色绘制各段路线。

请注意：“最短”仅指**固定首站、已选站点、指定交通方式、当前矩阵成本**的最小值；
并非全局最佳旅游计划。道路矩阵优化代价与第二次求路得到的实际分段
时间可能略有不同。返回优化前后矩阵时间、节约估算、各段/总道路距离
以及总交通时间；景点游览时长从现有 `places.visit_duration`
（如不存在则为 null）读取，全部存在时才给出包含游览时长的总时间估算。
没有官方开放时间、门票、公交班次、休息/用餐/停车数据，不虚构可行的全天日程。

如距离矩阵缺项、某些站点不可达、HTTP 请求出错或回传线路不完整，
返回 HTTP 502 **而不伪造道路路线**；数据库 POI 不存在时返回404，
重复景点返回422。原来的两站路线接口、直线预览、模式对比全部保留。
使用公共 Valhalla 演示服务有速率/容量限制，仅适合少量本地验证，
不要将其视为稳定的生产路线规划服务。

本地 `backend/.env` 中可选指定 `VALHALLA_MATRIX_URL`；
如果未设置，自动使用 `VALHALLA_ROUTE_URL` 所在服务的
`/sources_to_targets`，无需新的 DeepSeek Key。

### Windows 验收

```powershell
cd D:\smart-tourism
git fetch origin
git switch feat/poi-tourism-metadata-20261008
git pull --ff-only
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_road_itinerary.py"
node tests/frontend-workflow.mjs
cd frontend
npm run build
```

启动前后端后，在地图中将 3—6 个景点加入「我的路线」
（例如：南京博物院、南京总统府、夫子庙）；
保留第一个景点为起点，选择步行并点击「按道路时间优化多站顺序」。
检查路线折线是否沿街道而非蓝色直线、优化站点顺序、
道路里程/时间与已知游览时长是否显示。切换骑行、驾车后可
分别计算并缓存结果；增删景点则自动清空所有多站缓存。
如果路线无法计算，请截图右侧错误消息及后端请求状态；
不要将失败标记为0公里或0分钟。

可通过 PowerShell 验证接口（示例名称匹配均来自本地数据库）：

```powershell
$pois = (Invoke-RestMethod "http://127.0.0.1:8010/api/places").features
$names = @("南京博物院", "南京总统府", "夫子庙")
$ids = @($names | ForEach-Object {
    $name = $_
    $match = $pois | Where-Object { $_.properties.name -eq $name } | Select-Object -First 1
    if (-not $match) { throw "数据库缺少景点: $name" }
    [int]$match.properties.id
})
$body = @{ place_ids = $ids; mode = "pedestrian" } | ConvertTo-Json -Depth 4
$result = Invoke-RestMethod -Uri "http://127.0.0.1:8010/api/routing/itinerary" -Method Post -ContentType "application/json" -Body $body
$result.optimized_order_ids
$result.duration_minutes
$result.distance_km
$result.geometry.features.Count
```

自动化 CI 已验证 Python 单元测试与模拟前端路线工作流；
但公开 Valhalla 的多站矩阵和 Windows 实际地图显示
仍需要本地联网验收。


## 第九阶段：AI 个性化单日行程（DeepSeek × PostGIS × Valhalla）

新增 `POST /api/ai/itinerary`，并在左侧「AI 智慧文旅」面板增加
**生成 AI 个性化道路行程**按钮。用户填写自然语言需求，并可设置：
3—6个景点、3—12小时预算、预计出发时间、步行/骑行/驾车
（默认根据意图选择，少走路会优先考虑站间驾车）。

实现流程如下：
1. 使用现有 DeepSeek JSON 意图解析：严格校验景点类别、距离半径、
   偏好和游览天数；若没有密钥或模型失败，使用本地规则降级。
   明确提出的一天和低步行需求优先于模型推测。
2. 从 **PostGIS** 查询真实候选景点，并按当前地图中心的球面距离初选，
   使用库中存在的 `visit_duration` 和保守换乘缓冲做预算初筛；
   不相信模型编造的地点、经纬度或交通费用。选景阶段尚未对所有
   40+ POI 建立全局道路矩阵，因此不宣称全局最佳景点组合。
3. 使用现有 **Valhalla** `/sources_to_targets` 时间矩阵在选出的
   3—6站之间优化顺序（固定自动选中的第一站）；再用 `/route`
   获取逐段真实道路 GeoJSON。
4. 以分段道路时间及数据库已知的停留时长构建**暂定**到离时间；
   当停留时长未知时，后续时刻保持未知，`within_time_budget=null`；
   不将估计行程伪装成真实开放时间/预约时间。
5. 前端更新已选景点、交通方式、路线颜色和多站行程比较表，
   并在 AI 面板展示暂定时刻、推荐依据与未验证限制。
   用户继续手动修改路线时会清除旧的道路结果。

请求示例（经纬度为用户当前**地图中心**，非设备GPS）：

```json
{
  "query": "南京一天历史文化游，少走路",
  "lng": 118.7921,
  "lat": 32.0407,
  "max_stops": 4,
  "budget_hours": 8,
  "start_time": "09:00",
  "transport_mode": "auto"
}
```

`transport_mode` 可以省略，允许值 `pedestrian`、`bicycle`、`auto`。
返回 `ai_mode`、`intent`、`selected_places`（真实数据库POI）、
`itinerary`（道路时间矩阵顺序优化和实际 GeoJSON 线路）、
`timeline`（仅在数据足够时给出暂定时间）、
`within_time_budget`、`limitations`。
不足3个候选/不支持多日/时间预算跨午夜会返回422，
不可达路网或缺失路线返回502而不会伪造道路。
本阶段只支持单日行程、单一交通方式、固定首站，
未模拟实时拥堵、步行接驳、营业时间、等候与票价。
站间驾车并不保证进入景区后无步行需要。
DeepSeek 会接收用户输入的旅游偏好文本，不要填写个人敏感信息。

### 更新与验收

```powershell
cd D:\smart-tourism
git fetch origin
git switch feat/poi-tourism-metadata-20261008
git pull --ff-only

.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
node tests/frontend-workflow.mjs
node tests/ui-layout.mjs

cd frontend
npm run build
```

后端继续监听8010，前端继续在5173。
在左下方输入「南京一天历史文化游，少走路」，保持默认4站/8小时/09:00，
点击「生成 AI 个性化道路行程」，检查：
- 返回 `ai_mode=deepseek`（本地Key生效时），
  或 `rule_based`/ `rule_based_fallback`（规则降级）；
- 右侧路线面板中的景点均来自数据库且数量在3—6之间；
- 地图显示真实道路折线，暂定日程有到离时间或明确的未知标记；
- 交通方式和预算约束透明可见；
- 修改所选景点后，旧的 AI 路线失效，不会继续当作当前行程；
- 输入「南京两天游」应提示只支持单日；关闭公网道路服务应提示失败，
  不会显示0公里假数据。

GitHub Actions 对 Python 离线测试、前端模拟交互和 Vite 构建进行自动验证。
真正的公网 DeepSeek、南京数据库、Valhalla 矩阵及浏览器视觉效果仍须
本机验收，不能将 CI 通过视为生产环境保证。


## 第九阶段后续 UI 适配：AI 日程与景点列表分区

当 AI 生成4站以上行程时，左侧独立的景点列表、顺序预览和 AI 日程
曾同时占用有限窗口高度，导致 AI 文本与预览面板重叠。
当前改为**同一左栏的两个可切换选项卡**：

- **景点列表**：可滚动的真实 POI 列表 + 可折叠顺序预览。
- **AI 行程**：独立滚动的 DeepSeek 输入、时长/交通参数、暂定到离时间与限制。
- 点击顶部地图搜索、收藏或主题筛选会展示“景点列表”；
  完成 AI 景点检索后自动转至列表，生成 AI 行程后自动转至“AI 行程”。
  切换选项卡不会重新发送 AI 请求，也不会清除已规划道路。
- 右侧原有道路路线比较、推荐主题和统计面板保持不变。

这是一项布局与浏览状态修复，不改变 PostGIS 查询、DeepSeek Key、
Valhalla 路网及优化算法。
布局回归检查见 `tests/ui-layout.mjs`，
地图联动回归检查见 `tests/frontend-workflow.mjs`。
仍应在真实浏览器验证左右面板能正常滚动、选项卡可切换及4站行程全部可读。


## 第十阶段：可解释的多因素 AI 景点推荐（Draft）

本阶段在现有 `POST /api/ai/itinerary` 中替换了**仅按地图中心近距排序**
的景点候选选择器，API 请求格式、Valhalla 道路时间矩阵、已有两站/多站
手动路线、DeepSeek Key 与左右 UI 工作区均保持不变。

新的 `backend/app/ai/recommendation.py` 在查询出的真实 PostGIS POI（最多100条）
中，综合以下**可核实或可明确标注的启发式指标**逐站选择3—6个景点：
- **兴趣匹配**：经过白名单校验的旅游类别；使用原有 DeepSeek 意图识别，
  Key 缺失时仍可按规则理解类别；
- **有来源的语义匹配**：只有 `places.tags` 中确实存在、且与用户关键词对应的
  标签才加分。不存在的标签、缺失的室内外属性、营业时间、评分等绝不补造；
- **类别多样性**：鼓励选择不同类别，减少附近同质景点重复；
- **空间紧凑性**：地图中心和已选景点的球面直线距离作为候选期近似值，
  **不能把它当作步行、骑行或驾车距离**；
- **停留时间和数据完整性**：有 `visit_duration` 时进行预算初筛，
  换站30分钟只是候选过滤用的粗预留，不作为真实道路耗时；
  最终时间仍由 Valhalla 实际道路折线与数据库已知停留时长计算。

候选入选是**确定性的贪心启发式**（`explainable_greedy_v1`），并不宣称在全部
南京景点组合上实现全局最优。首站是评分最高的候选景点，而 Valhalla 只负责
在这几个已选真实站点之间优化最短道路交通时间。公共 Valhalla 服务的覆盖
与稳定性限制仍然存在。

**返回结果增强：** 每个被选中 POI 的 `properties.recommendation` 包含相对分数、
类别匹配、数据库标签命中、距离近似、室内外证据及推荐理由；
`timeline[].reason` 展示同一依据。
`recommendation_summary` 则说明推荐了多少类景点、多少景点的实际资料标签
和需求词命中。前端 AI 行程面板支持查看“为什么推荐这些景点”与评分依据。
分数仅是可解释的规则评分，**不是景点星级、客观质量或模型置信度**。

### 推荐质量回归与测试

```powershell
cd D:\smart-tourism
git fetch origin
git switch feat/poi-tourism-metadata-20261008
git pull --ff-only

.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_recommendation_quality.py"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
node tests/frontend-workflow.mjs
node tests/ui-layout.mjs

cd frontend
npm run build
```

可用同样需求比较旧版与新版（例如「南京一天历史文化游，喜欢博物馆和古迹，
不想走太多路」）；重点查看新路线是否包含不同类别、每站推荐理由是否有
数据库可追溯依据，以及是否仍符合时间预算。该阶段没有引入外部景点
人气/权威评分数据；真实用户满意度或 A/B 测试尚未进行，
因此不能声称推荐效果已在实际游客中获得提升。


## 第十一阶段：AI 单日行程动态编辑与真实道路重新规划（Draft）

本轮在原来的 AI 一日游推荐页面加入 **调整当前行程** 区域。初次生成行程后，
可以锁定必去景点、从 PostGIS 已收录的真实 POI 中选择替换地点、
删除非锁定景点，并修改既有的出发时间、时间预算和步行/骑行/驾车模式。
点击「重新规划已调整行程」才会真正改动地图显示，防止把尚未计算的编辑
误当作已验证道路。右侧路线仍使用既有 MapLibre/Valhalla 图层。

**新的 API：** `POST /api/ai/itinerary/replan`

```json
{
  "place_ids": [1, 2, 3, 4],
  "locked_place_ids": [2],
  "transport_mode": "auto",
  "budget_hours": 8,
  "start_time": "09:00",
  "auto_trim": true
}
```

其中 ID 必须属于本地 PostGIS 的真实景点，不能传自由输入的经纬度。
第一站始终固定为起点；锁定意味着必须保留该景点，
**不是**固定它在中间行程的顺序。每次修改会重新读取数据库、
调用 Valhalla 道路时间矩阵与真实多段路线，**不复用旧道路距离**。
重新规划不需要再次调用 DeepSeek，因此不额外消耗大模型 Token。

- **自动删减**：若已知停留时间超出预算，先移除末尾未锁定站点，
  避免无效的外部路网调用；若实际道路时间使行程超时，再继续移除并
  重新计算道路。最多删减到3站。删减顺序是**确定性简易规则**，
  不是全局最优的景点组合选择。
- **不能满足约束**：如果起点、锁定站点和至少3站仍超预算，
  API 返回 `409 Conflict`，不会悄悄删除锁定地点。
  关闭 `auto_trim` 时，若实际道路结果超预算，系统会保留全部站点，
  但清楚标明 `within_time_budget=false`。
- **资料未知**：景点缺少可信游览时长时，不编造离开时刻；
  仅当已知停留时间 + 实际道路时间的**下界**已超预算时，
  才可以断定不满足预算。否则返回 `within_time_budget=null`。
- **错误处理**：不存在的 ID 返回404；重复 ID、低于3站、
  超过6站、跨午夜等返回422；路网失败返回502。
  失败时不会替换上一版成功的地图道路线路。
- **同步操作**：用户在地图中手动修改行程后，AI 面板会提示旧日程与
  地图不一致，并提供「同步地图已选景点」；此时仍需重新规划后
  才能获得新的道路距离和时间。替换下拉框会按需从
  `GET /api/places` 加载实际数据库 POI。
- **限制**：暂不验证营业时间、门票/预约、休息、停车及实时交通，
  最多6站，单日、单模式，不能当作真实导航服务。

### Windows PowerShell 更新与测试

```powershell
cd D:\smart-tourism
git fetch origin
git switch feat/poi-tourism-metadata-20261008
git pull --ff-only

.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_ai_itinerary_edit.py"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
node tests/ai-edit-workflow.mjs
node tests/frontend-workflow.mjs
node tests/ui-layout.mjs
cd frontend
npm run build
```

前后端启动后，在「AI 行程」生成4站南京旅游行程，再展开左侧下方
「调整当前行程」：
1. 将一个非首站设为锁定必去；
2. 加载真实景点，替换另一个非锁定站点；
3. 将预算从8小时缩到6小时，保持自动减站；
4. 点击重新规划，确认地图出现**重新计算的道路**、右侧行程更新，
   以及锁定景点仍然保留。
5. 将所有站点锁定并将时间设得过短，确认409错误有明确提示，
   且上一次道路不被覆盖。
6. 修改交通方式或地图已选景点，确认旧时间不会被无提示地沿用。

Github Actions 只覆盖无密钥、无真实数据库和无公共路网请求的
单元/模拟交互测试；南京真实地点替换、超时删减与浏览器交互
仍需要本机端到端验收。


## 第十二阶段：AI 多轮对话修改行程（预览→确认→重新规划）

在已生成 AI 一日游行程后，左侧「AI 行程」中新增**AI 多轮行程助手**（默认折叠，
点标题展开）。助手不是无约束聊天生成攻略，而是把自然语言转换为
**经过 PostGIS 校验的结构化行程编辑建议**。

### 操作流程

1. 从 DeepSeek（无Key或请求失败则使用安全规则降级）提取有限的编辑操作：
   锁定 / 解锁 / 替换 / 移除景点、步行骑行驾车模式、3—12小时预算、出发时间。
   例如：「第二站换成玄武湖公园，第三站必须保留」。
2. 请求 `POST /api/ai/itinerary/chat/preview`（**只读预览**）。
   后端重新从PostGIS读取当前景点及候选景点，校验真实ID、真实名称、
   修改站点、是否首站、是否锁定、最少3站、预算和午夜限制。
   如按兴趣类别替换（例如「第二站换成自然风光类」），只从数据库存在的类别
   和真实景点中确定性选择，按与原站点的球面距离近似排列候选；
   此处**还没有计算实际道路**。具体景点名优先按数据库精确匹配。
3. 前端展示变更清单、拟保留站点、交通方式和时间预算。
   **取消**或继续提出新问题不会修改地图；新的未确认指令会丢弃上一份预览。
   提出互相矛盾的条件会得到明确提示，而不是擅自解除锁定。
4. 用户点击「确认修改并重新规划」后，才调用已经验收的
   `POST /api/ai/itinerary/replan`，通过Valhalla重新计算道路矩阵与
   多段实际路线，并在成功后更新原有地图、右侧路线面板和AI日程。
   路网失败或预算冲突时，**原有有效路线不变**。
5. 对话保留最近最多6条简短历史帮助解析后续要求；对话只在浏览器
   当前页面内维护，不在服务器持久保存。确认后可以继续输入下一轮。
   若对话期间地图或手动编辑发生变化，旧预览及异步返回结果会被阻止应用。

可发送的测试话术：
- 「第二站换成玄武湖公园」— 景点精确匹配，需确保玄武湖尚未入选；
- 「第三站必须保留」— 必去景点锁定；
- 「改成骑行，预算调整为6小时」— 下一轮修改已有行程；
- 「取消锁定第三站」— 解锁操作；
- 「删除第四站」— 仅当现有站点≥4且该站未锁定时可执行。

**设计边界：** 不会调用模型自动执行数据库写入、编造POI或道路。
DeepSeek仅解析编辑意图，路径信息依然由PostGIS和Valhalla确定；
若无Key，规则降级能覆盖部分明确指令，但并不是通用闲聊或完全
自由表达的聊天机器人。预算/营业时间/公共交通限制与上一阶段相同。
聊天文本在配置Key时会发送给DeepSeek，请勿输入隐私信息；
仓库不存放或提交Key。

### Windows 验收

```powershell
cd D:\smart-tourism
git fetch origin
git switch feat/poi-tourism-metadata-20261008
git pull --ff-only
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_ai_conversation.py"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
node tests/ai-chat-workflow.mjs
node tests/ai-edit-workflow.mjs
node tests/frontend-workflow.mjs
node tests/ui-layout.mjs
cd frontend
npm run build
```

重启后端（新增API），前端刷新。先用「南京一天历史文化游」生成4站AI行程，
在「AI 多轮行程助手」输入「第三站必须保留」并点击「预览修改」，
检查地图没有变化；点「确认修改并重新规划」检查保留锁定及实际路网。
第二轮输入「改成骑行」并再次确认；再试一次取消预览。
最后尝试锁定冲突、将起点删除及手动改地图之后点击旧确认按钮，
确保系统阻止过期操作。公共Valhalla实际可用性仍需联网验收。

离线回归：`tests/test_ai_conversation.py`、
`tests/ai-chat-workflow.mjs`、`tests/ui-layout.mjs`，由
`.github/workflows/ci.yml` 自动执行。PR保持Draft，不合并main。


## 第十三阶段：景区入口资料与道路位置审计

这轮不再假定 `places.geom` 一定是景区入口。针对玄武湖、紫金山、栖霞山、
红山森林动物园等面积较大的区域，**景点展示点**与**适合某交通方式寻路的出入口**
可能是不同位置。入口数据须有来源，且有人工复核记录，不能通过AI猜坐标。

### 已实现的功能

- 可选数据库迁移 `database/migrations/add_routing_access.sql`：
  给现有PostGIS `places` 表添加可空 `routing_access JSONB`。
  `places.geom` **保持原值不变**（红色景点标记和空间检索不受影响）。
- `backend/app/access_points.py` 根据 `pedestrian`、`bicycle`、`auto`
  分别选择入口点。要求状态 `reviewed`、来源URL、日期、真实经纬度和入口名称，
  且入口位于对应POI原坐标**10 km以内**；拒绝异常坐标、过期的未来日期、
  未审核、无来源或其他交通方式的入口资料。该程序检查格式和空间合理性，
  **不会打开来源网页核实内容真实性**。
- 两站 `POST /api/routing/route` 和多站 `POST /api/routing/itinerary`、
  `POST /api/ai/itinerary`、`POST /api/ai/itinerary/replan` 经过同一
  寻路核心后，均会使用当前交通方式对应的合格入口点；
  Valhalla道路时间矩阵和折线使用的是**同一组入口坐标**。
- 若未配置有效入口，无论是否运行了迁移都**回退为原POI坐标**。
  API 的 `routing_points` 记录每一站使用 `reviewed_access_point`
  或 `poi_coordinate_fallback`，并包含已有入口的审核日期、来源和坐标。
- 右侧「我的路线」新增折叠的**道路入口资料**，显示各站审核覆盖情况、
  未核实的回退情况和可查看的来源；地图上的**紫色圆点**只代表已审核入口，
  红色圆点仍是景点原位置。手动更改线路会清除旧入口标记。
- 新增只读 `GET /api/routing/access-coverage`：
  按步行、骑行、驾车分别统计已审核入口覆盖率及逐个POI的回退状态。

### Windows PostgreSQL 迁移（安全、可选）

若不做迁移，原系统也能正常寻路；只是不会使用入口资料。

1. 在 **pgAdmin** 打开 smart-tourism 对应的本地PostgreSQL数据库，
   选择 Query Tool。
2. 打开项目中的 `database/migrations/add_routing_access.sql`，
   复制其中SQL并执行一次。该迁移不删除、不移动原有POI坐标。
3. 确认字段已存在：

```sql
SELECT name, geom, routing_access
FROM places
WHERE name IN ('玄武湖公园', '紫金山', '红山森林动物园');
```

4. 在浏览器打开 `http://127.0.0.1:8010/api/routing/access-coverage`。
   如果尚未逐条补入真实入口，统计为0是**正确结果**，不是寻路失败。

### 人工补充入口资料的格式

单条 `routing_access` 应为 JSONB 对象，按交通方式分别保存独立入口：
例如已核查的步行入口使用 `pedestrian`，汽车能到达的入口使用 `auto`。
**绝不可将公园几何中心、在线路线吸附结果、AI回答中的经纬度直接标成入口。**

建议人工记录字段：

| 字段 | 示例/要求 |
| --- | --- |
| 模式 | `pedestrian` / `bicycle` / `auto` |
| `status` | 初始 `draft`；经过人工核验后才可以填 `reviewed` |
| `name` | 经过核对的入口名称 |
| `lng`, `lat` | 来源明确的WGS84十进制度经纬度，顺序为经度、纬度 |
| `source_url` | 可回查的地图、景区公告或权威资料网页URL |
| `reviewed_on` | 人工核对日期，如 `2026-10-10` |

保留缺失状态的**安全草稿**（不含任何捏造坐标）：

```sql
UPDATE places
SET routing_access = COALESCE(routing_access, '{}'::jsonb)
    || '{"pedestrian":{"status":"draft"}}'::jsonb
WHERE name = '玄武湖公园';
```

这只会创建**不可用于寻路的草稿**，路线仍按照 `places.geom` 计算。
只有人工核实入口的坐标、名称、交通方式、URL和日期之后，
再将其对应模式替换为完整 `reviewed` 记录。
迁移及示例SQL均不会创建已核实的南京景区入口；目前仓库没有可证明
每个景点入口的坐标来源，因此**不会自动批量填充40条景点**。

### 回归检查与本机验收

```powershell
cd D:\smart-tourism
git fetch origin
git switch feat/poi-tourism-metadata-20261008
git pull --ff-only

.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_routing_access.py"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
node tests/frontend-workflow.mjs
node tests/ui-layout.mjs
cd frontend
npm run build
```

重启FastAPI、刷新前端，选2—4个景点分别计算步行和驾车路线。
**未录入入口时，右侧应显示全部采用原坐标，地图不出现紫色入口标记**；
这说明回退机制正常。日后录入一条经过人工审查的真实入口后，
再次计算对应交通方式线路，右侧审核覆盖数增加，地图在相应位置出现
紫色圆点；其他交通方式仍使用原坐标或其单独核验入口。
本轮CI通过的是离线合成坐标模拟，不代表真实出入口已核实，
也不保证景区开放、通行或公共Valhalla的实时准确性。


## 第十四阶段：玄武湖真实入口研究——候选证据、坐标系与人工审核（首批）

2026-10-10首批证据已整理，但**尚未达到把经纬度标记为 `reviewed`
并用于 Valhalla 正式寻路的条件**。用户的本地
`GET /api/routing/access-coverage` 已验证40个POI、步行/骑行/驾车的
审核覆盖数均为0，属于正确的安全回退状态。

本轮GitHub新增：
- `data/entrance_evidence/xuanwu_lake_20261010.json`：
  玄武门、解放门的景区官方与地图链接、坐标原始来源、
  坐标系标记、候选门址及待复核清单。
- `database/reviews/xuanwu_lake_20261010_draft.sql`：
  **可选**草稿入库SQL。只存名称和可查来源，永不写入路由可识别的
  `reviewed` 状态或入口 `lng/lat`，且不覆盖已有已审核记录。
  **暂时无须运行；仅当你希望把核查进展存在本地PostGIS时才执行。**
- `tests/test_entrance_evidence.py`：
  检查候选仍为 `draft`、高德原始坐标明确标注非WGS84、
  自动驾驶入口未被臆造、草稿SQL不得激活寻路点。

### 已收集并交叉核查的具体信息

| 候选 | 证据 | 坐标状态 | 当前结论 |
| --- | --- | --- | --- |
| 玄武湖景区玄武门 | [景区游客中心名单](https://www.xuanwuhu.net/lyfw/lyfw2.aspx)、[高德景区门](https://www.amap.com/place/B00190B4FQ) | 高德页面显示纬度32.070519、经度118.787506，**不可直接当WGS84** | 候选步行入口，待核验公园步道交汇点 |
| 玄武湖景区解放门 | [景区解放门咨询点](https://www.xuanwuhu.net/lyfw/detail.aspx?id=207)、[高德景区门](https://ditu.amap.com/place/B0019095PK) | 高德页面显示纬度32.062228、经度118.796638，**不可直接当WGS84** | 候选步行入口，待核验公园入口步道 |
| 南京城墙玄武门 | [Wikidata Q17059567](https://www.wikidata.org/wiki/Q17059567) | 文物门址经纬度为WGS84参考值，经度约118.782338889、纬度约32.072619444，且条目**没有坐标引用** | 仅用于交叉识别地标，不能自动认定为可通行公园入口 |
| 机动车可到达位置 | [南京市玄武湖景区保护规定](https://www.nanjing.gov.cn/zdgk/201712/t20171229_1057120.html)、[玄武区交通改造报道](https://www.xwzf.gov.cn/ztzl/yshjgzzl/gzdt_69308/202411/t20241127_5019911.html) | 尚无可审核的机动车落客点WGS84坐标 | 不创建 `auto` 入口 |

注意：高德中国地图通常使用GCJ-02坐标系，和项目PostGIS、
MapLibre/OSM依赖的WGS84存在系统偏移。**不能把平台坐标直接
复制到 `routing_access.pedestrian.lng/lat`**。
仅有一个城门纪念性地标的经纬度也不代表它恰好落在景区可穿行入口。

### 后续人工审核标准

玄武湖至少先核实一个**实际可步行穿越的门位及连接道路节点**：

1. 在高德入口页面核对名字及园区入口位置，排除景点中心点或城墙售票点；
2. 在开源WGS84路网/航片上找到**同一个**实际通道，必要时按
   GCJ-02→WGS84进行带精度说明的坐标转换，并检查其步道连通性；
3. 在本地PostGIS核算入口与对应 `places.geom` 的球面距离
   不超过现有10km安全上限。**10km只是防错上限，不代表坐标准确。**
4. 检查近期官方开放/通行规定。汽车路线应独立审核停车或允许落客点，
   **不能把步行门坐标直接复用给 `auto`**；
5. 来源、地点、交通方式和日期均经过人工核对后，才把其中一个确定
   入口按第十三阶段的字段格式升级为 `reviewed`。然后通过
   两站/多站实际Valhalla路由对比复测。

当前无需再次执行 `ALTER TABLE`，数据库结构与原40条POI保持原样；
也不会因为新增候选文件而导致前端突然出现紫色入口标记。


## 第十四阶段·空间复核：GCJ-02→WGS84和OSM步行门节点审计

在之前两处玄武湖入口的初步来源审查基础上，新增了一个**只读、可本机复现的空间审核工作流**。
目前**未得到真实OSM闸门/步道节点的在线响应，因此尚未完成“可通行入口”的认证**。
任何结果都不会自动升级为 `reviewed`，不会运行SQL、改变PostGIS或影响Valhalla路线。

### 已完成的坐标转换（仍属草稿）

使用标准的 GCJ-02 → WGS84 迭代逆变换计算高德两处原始标点：

| 候选 | GCJ-02 原始经度/纬度（高德） | WGS84转换结果经度/纬度 | 核验状态 |
|---|---|---|---|
| 玄武门 | 118.787506 / 32.070519 | **118.78229935 / 32.07257793** | 尚未证明与实际可通过的OSM步道相连 |
| 解放门 | 118.796638 / 32.062228 | **118.79144511 / 32.06429665** | 尚未证明与实际可通过的OSM步道相连 |

玄武门转换点与 [Wikidata城门地标](https://www.wikidata.org/wiki/Q17059567)
提供的坐标相差约 **5.9米**，构成一个地标层面的空间一致性线索，
**但Wikidata原坐标缺少引用来源、城门与真实游园通行点并不必然一致**。
算法坐标精度不等于实地门位精度。

仓库中的
`data/entrance_evidence/xuanwu_lake_unreviewed_wgs84_estimates.geojson`
包含2个**未认证**的WGS84转换标点，可在QGIS中直接加载进行目视复核；
不会进入前端正式入口图层或PostGIS的 `reviewed` 字段。

### 新增可复现的 OSM 步道/闸门核查脚本

`scripts/audit_xuanwu_osm.py` **只通过HTTPS读取OpenStreetMap Overpass**
真实闸门节点和附近的步行路段，评估：
- `entrance`、`barrier=gate`、`kissing_gate`等OSM节点及标签；
- 节点距已转换的高德候选点的球面距离；
- 节点是否属于允许步行的 OSM way（检查节点ID是否真正属于way的nodes），
  并排除 `foot=no`、`access=private/no`；
- OSM节点详情可打开的链接、潜在无障碍/开放限制；
- **未作的验证**：OSM图纸并不能自动证明门禁开放、入口合法、实时通行，
  也不能替代实际Valhalla路由和人工审核。

**Windows PowerShell：**

```powershell
cd D:\smart-tourism
git fetch origin
git switch feat/poi-tourism-metadata-20261008
git pull --ff-only

.\.venv\Scripts\python.exe scripts\audit_xuanwu_osm.py --online
```

成功后会生成两个文件（`*_local` 已加入.gitignore，不会自动提交）：

1. `data\entrance_evidence\xuanwu_lake_osm_audit_local.json`，
   包含两个入口的搜索范围、OSM节点ID、来源链接、位置距离、道路关联程度、
   被禁止步行的标签及所有审核警告；
2. `data\entrance_evidence\xuanwu_lake_osm_audit_local.geojson`，
   是QGIS可打开的地图点位：原始高德转换草稿和找到的OSM闸门候选，
   **全部标记未审核**。

导入QGIS：菜单「图层 → 添加图层 → 添加矢量图层」选择生成的GeoJSON；
坐标使用WGS84（EPSG:4326）。与OSM底图叠加，检查各点是否真的位于
对应景区门的步行通道，排除附近地铁口或城墙地标。

**如果Overpass访问失败**，可以先在PowerShell离线导出两处查询语句，复制到 [Overpass Turbo](https://overpass-turbo.eu/) 网页执行：

```powershell
.\.venv\Scripts\python.exe scripts\audit_xuanwu_osm.py --queries-only
```

网页导出的Overpass JSON按候选ID保存到本地目录中的
`xuanwumen_west.json` 和 `jiefangmen_south.json`，
再用下面的离线解析命令。

**如果Overpass访问失败**（例如429、连接超时），脚本会明确报错，
不会创建虚假OSM节点或更新数据库。可以稍后重试，或通过网页版
[Overpass Turbo](https://overpass-turbo.eu/) 手动执行JSON报告中的
`osm_query` 查询（实时在线运行失败时可以参考脚本的 `build_query`）。
也可以从已有外部OSM工具取得这两处区域的Overpass JSON，
保存为 `xuanwumen_west.json`、`jiefangmen_south.json` 后运行：

```powershell
.\.venv\Scripts\python.exe scripts\audit_xuanwu_osm.py --osm-json-dir D:\osm-gate-snapshots
```

此脚本不依赖DeepSeek或PostGIS，不需要数据库迁移，
且可通过 `python -m unittest discover -s tests -p "test_xuanwu_osm_audit.py"`
进行纯离线自检。

**审核标准**：必须先在QGIS/OSM确认至少一个候选确实是
可从城市步行网络进入湖区的开口，并核验可靠的近期来源及景区开放安排。
确认前 **不要** 手动写 `status=reviewed` 或将近似转换点当作导航入口。
机动车落客点尚无独立验证，不进行 `auto` 入口设置。

下一步可将本机生成的JSON或QGIS截图发回；再根据实际OSM闸门节点、
交通方式和景区官方资料，逐个确定可认证的入口，生成有回滚说明的SQL，
并实测入口使用前后的 Valhalla 路程。


## 第十四阶段·Overpass超时处理：原生OpenStreetMap JSON地图接口

2026-10-10 本地环境反馈：默认Overpass返回 HTTP 504、备用服务器返回500，
Overpass Turbo浏览器页面也报告 OSM3s Dispatcher 读取和索引等待超时。
这是服务器不能及时处理查询，不能据此判断南京景区没有入口数据。
为避免在繁忙公共Overpass实例反复提交同一查询，新增
**不依赖 Overpass QL 的原生 OpenStreetMap API 只读小范围下载模式**。

### 推荐首先运行此命令

```powershell
cd D:\smart-tourism
git pull --ff-only
.\.venv\Scripts\python.exe scripts\audit_xuanwu_osm.py --osm-api
```

`--osm-api` 对玄武门和解放门分别发起一次
`GET https://api.openstreetmap.org/api/0.6/map.json?bbox=左,下,右,上`，
每个范围默认约为360m×360m（覆盖此前180米半径）。
OSM官方API提供JSON原生导出：只要求bbox而不执行Overpass数据库筛选。
数据包含附近OSM节点/道路及其标签，随后由**同一套本地分析代码**
识别 `entrance/barrier`、步道节点与 `foot/access` 标签。
这只适用于此次小规模人工核查；OSM编辑API不适合大面积
高频抓取，且可能仍存在服务限制。

若成功，将输出以下**未审核的本机结果**：

```text
data\entrance_evidence\xuanwu_lake_osm_audit_local.json
data\entrance_evidence\xuanwu_lake_osm_audit_local.geojson
```

如果连OSM原生接口也不能在PowerShell访问，执行：

```powershell
.\.venv\Scripts\python.exe scripts\audit_xuanwu_osm.py --osm-api-urls-only
```

命令会打印两条预填bbox的官方OSM JSON下载地址；
在Chrome中分别打开、将原始JSON保存为
`xuanwumen_west.json` 和 `jiefangmen_south.json`，
统一放到 `D:\osm-gate-snapshots` 目录后执行：

```powershell
.\.venv\Scripts\python.exe scripts\audit_xuanwu_osm.py --osm-json-dir D:\osm-gate-snapshots
```

仍然失败时不要伪造OSM数据；可以将具体错误文本/浏览器截图发回继续排查。
**不需要重启WebGIS、重新运行数据库迁移或执行draft SQL。**
任何研究结果都不会自动写入 `reviewed`，OSM步道关联也不能代表
实际开放状态。对任一候选正式启用入口前仍需人工复核来源和现场通行。


## 第十四阶段·真实OSM节点审阅：解放门未连通候选与线段距离复核

用户本机已成功从OSM原生 `map.json` 接口获取玄武门和解放门周边真实数据；
具体实测结果及审计结论见
`data/entrance_evidence/xuanwu_lake_osm_initial_review_20261010.md`。
初次审计在玄武门周边发现13条脚本认定的步行way、0个显式闸门；
解放门周边22条步行way、1个
[OSM node 12325223492](https://www.openstreetmap.org/node/12325223492)
（`entrance=yes`，经纬度118.790473,32.063818）。
此节点与转换后的高德标点约105.9m，但不属于已筛选步行way的节点列表；
到最近步行way**节点**约43.4m，故还不能认定其可作为游园入口。

最新版研究脚本增加了**最近可步行way线段**的几何投影距离，
区别于原来的最近节点距离；并支持将两处的原始OSM JSON保存供逐条审核。

```powershell
cd D:\smart-tourism
git pull --ff-only
.\.venv\Scripts\python.exe scripts\audit_xuanwu_osm.py --osm-api --save-osm-snapshots
```

除以前生成的 `xuanwu_lake_osm_audit_local.json` 和 `*.geojson` 外，还会得到
`data\entrance_evidence\xuanwu_osm_raw_local\xuanwumen_west.json`
和
`data\entrance_evidence\xuanwu_osm_raw_local\jiefangmen_south.json`。
前者便于研究无闸门标注时附近OSM步道如何穿越门位，后者便于核实
`12325223492` 与附近ways的真实关系。均为OSM来源数据，
按ODbL要求标注© OpenStreetMap contributors。

请只分享审计JSON与必要的OSM原始片段；不要在未经地图和通行证据核实之前
向 `routing_access` 填入 `reviewed` 或把最近道路投影点直接当入口。
本次代码仅扩展只读分析，不改变已有40个POI、PostGIS或Valhalla参数。
