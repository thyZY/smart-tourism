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


## 新功能开发：Sprint 1–5（feat/itinerary-management-20261014）

> 注意：本分支由较早版本main派生，**不包含**
> `feat/poi-tourism-metadata-20261008` 上的完整 Valhalla、AI 对话及入口人工审核功能。
> 两套分支不要混淆；本分支当前的主线是独立实现的单日AI候选景点 + 安全恢复/导出。

### Sprint 1：真实 POI 的单日 AI 行程与地图显示

- `POST /api/ai/itinerary/generate` 输入旅游需求、类型、同行人员、步行强度、
  2–6个景点与交通方式；
- 从PostGIS `places` 表读取真实记录，DeepSeek**仅可重排已查到的ID**；
  不允许AI直接决定不存在的景点名、经纬度、交通时间；
- 缺少API Key、模型失败或非法输出时自动切换到**明确标识的本地类别规则排序**。
  `planning_method` 可区分AI排序和规则回退；
- `backend/app/ai/itinerary_geo_service.py` 可选向本机Valhalla请求多站路线；
  只有响应、分段和polyline6解码都通过校验才设置
  `route.status=verified_by_routing_service`；
- 未配置Valhalla时仍可在MapLibre显示**直线顺序预览**，
  界面明确注明这**不是道路导航**，绝不输出虚构道路耗时。

### Sprint 2：用户确认的轻量行程调整

已实现“减少站点并预览”后再由用户点击“确认替换当前行程”；
预览阶段不会修改主地图。当前尚不是完整自由多轮AI编辑，
不能保证减少站点必然降低步行量；如需“锁定站点/口头多轮约束”
须下一轮进一步开发并接入实际道路时间矩阵。

### Sprint 3：我的行程（仅浏览器本地）

- 最多保存15条只含ID/交通方式等必要信息的本地快照；
- 重新打开页面可恢复快照列表；
- 恢复时通过 `POST /api/ai/itinerary/restore` **从当前数据库重查景点**，
  保留保存的ID顺序。失效ID报409，不擅自使用旧坐标；
- 再次调用可用的Valhalla路线服务，无法计算时降级为直线预览。
- 清理浏览器数据或换设备会丢失记录；尚无云端账号同步。

### Sprint 4：旅行成果导出

- 生成包含当前数据库景点的行程JSON；
- 浏览器打印报告（打印菜单可选“另存为PDF”），含站点、类别、来源和局限；
- **只有Valhalla验证成功**才可下载路线GeoJSON，直线不伪装为道路。
- 尚未提供真实开放时间、实时交通、景区无障碍承诺或拍照地图PDF。

### Sprint 5：旅游资源 GIS 分析驾驶舱

- 在经纬度0.02°格网上统计真实POI数量、不同类别计数、
  Top 3集中格网和图形定位；
- 可导出GeoJSON供QGIS复核；
- **这些是角度格网的资源数量统计**，不是等面积统计，
  也不是实际客流、设施覆盖率或服务盲区。

### 需要本机验证的项目（不能由无密钥 CI 代替）

在Windows PowerShell项目根目录：

```powershell
git switch feat/itinerary-management-20261014
git fetch origin
git pull --ff-only origin feat/itinerary-management-20261014
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_ai_itinerary_management.py -v
node tests/frontend-workflow.mjs
node tests/ai-itinerary-ui.mjs
cd frontend
npm ci
npm run build
cd ..
```

两个终端分别执行`./start-backend.ps1`和`./start-frontend.ps1`，
打开 http://localhost:5173。点击右侧“展开 AI 行程 · 保存 · 报告”。

建议实际验收顺序：

1. **无API Key测试（可临时在本地控制配置，但不要提交或发截图）**：
   仍能选择至少2个真实数据库POI；排序方式为本地规则；
2. **已有DeepSeek Key**：实际点击生成时才会调用 DeepSeek API，
   可能消耗你账户额度。应确认返回的是数据库真实景点，不能额外冒出景点；
3. **地图**：显示相应已查询景点，默认直线预览应明确标识；
4. **Valhalla（可选）**：若本机有Valhalla实例，在你自己的`backend/.env`配置
   `VALHALLA_URL=http://127.0.0.1:8002`（端口以真实部署为准），重新启动后端。
   仅服务实际成功时才显示道路距离、分钟数和可导出道路GeoJSON；
5. **编辑预览**：点击“减少景点并预览”，地图原路线必须保持不变，
   直到点击“确认替换当前行程”；
6. **保存恢复**：保存当前行程，刷新F5，点击“恢复并核实”，
   能重新从PostGIS解析景点；如果旧ID不存在，应显示错误并保留原路线；
7. **导出**：下载行程JSON、使用浏览器打印“另存为PDF”，
   无真实道路时GeoJSON道路按钮禁用；
8. **GIS驾驶舱**：显示格网 → 点击Top格网定位 → 导出
   `nanjing-poi-grid-observed.geojson` → 使用QGIS加载。

### 安全与测试范围

CI不设置DeepSeek Key、不连接真实PostGIS和Valhalla。
已有单元测试采用模型和网络模拟，验证API ID白名单、恢复错误、
OSM/Valhalla几何解码契约，以及现有前端工作流和编译。
**CI通过不等于真实在线服务已验收**。

`backend/.env`被仓库的`.gitignore`排除；本轮从未提交或读取私人Key。
如果要让DeepSeek真实生效，应仅在你自己的电脑配置密钥。


### 2026-10-15：UI 布局整合（避免面板遮挡）

主界面已调整为顶部两层工具栏、左侧景点浏览、中央 MapLibre 地图、
右侧**单功能标签工作台**。此前的 AI 行程、我的路线、主题推荐、文化线路、
景点统计、GIS 空间分析，以及点选后显示的景点详情均保留，
但不再以多个绝对定位浮窗同时覆盖地图。左右工作区可通过顶部按钮折叠，
顶部分类栏可以水平滚动。较窄的屏幕改为地图、景点列表、工作台依次纵向排列。

**Windows 本地界面验收：**

```powershell
# 从项目根目录运行（与另一个后端终端分开）
git fetch origin
git pull --ff-only origin feat/itinerary-management-20261014
node tests/ui-layout.mjs
node tests/frontend-workflow.mjs
node tests/ai-itinerary-ui.mjs
cd frontend
npm ci
npm run build
npm run dev -- --host localhost --port 5173 --strictPort
```

浏览器访问 http://localhost:5173 并检查：

1. 桌面 1600×900 或 1920×1080：顶部搜索、附近、收藏、当前区域、
   地图模式与类型筛选均显示；中间地图未被主题/文化/统计等面板遮挡；
2. 左侧景点列表 40 项可独立滚动，不盖住右侧功能；
3. 右侧逐个切换：AI行程、我的路线、主题推荐、文化线路、景点统计、
   空间分析；点选左侧一个景点后自动打开「景点详情」；
4. 「隐藏景点」与「隐藏工作台」可扩大地图；再次显示能恢复功能；
5. 在 1280、1024、768、390 CSS 像素宽度检查缩放/排版：
   较窄屏幕区域垂直堆叠，避免卡片叠压，地图仍可访问；
6. 测试 AI 生成/恢复，及分析格网显示、隐藏与导出，不应改变原有业务数据。

**自动 CI 只检查源结构、状态行为和构建，不代替真实浏览器像素级截图检查。**


## WebGIS v1.3：聚合地图与交互式行程（开发分支）

**开发分支**：`feat/webgis-v1.3-map-interaction-20261015`，
基于已验收 UI 的 `feat/itinerary-management-20261014` 创建。
未合并 `main`，且没有改变 `backend/.env`、数据库或 DeepSeek 调用方式。

### 本轮功能

- **POI 自动聚合**：MapLibre 使用新增的 `places-clusters` 聚合 GeoJSON 数据源；
  zoom≤13 的密集景点缩并为蓝色数量圆点。点击聚合点自动放大到展开级别，
  放大后恢复橙红色单景点标识，鼠标悬停显示景点名；
- **原始数据不变**：`places` 原始 GeoJSON 数据源继续为热力图提供真实每个 POI，
  搜索、附近、分类、收藏等路径同时更新聚合视图；不将聚合数量当作热度；
- **已选 POI 高亮**：详情打开时增加橙色独立高亮环，地图和列表选中状态同步，
  关闭详情可清除；
- **行程站点序号**：从选择顺序生成独立的 `route-stops` GeoJSON 源，
  蓝色 1/2/3… 圆点保留在地图上；左侧搜索结果显示「第 N 站」；
  「我的路线」页可点对应景点以定位地图并打开详情；
- **AI 工作台简化**：打开「AI 行程」标签即可填写旅游需求、生成并管理行程，
  不再需要额外点「展开」；
- **聚合图层不改变路线真实性**：蓝色序号代表停靠顺序；
  只有 Valhalla 返回校验通过的路网才能标注道路距离，否则仍标记为直线预览。

为栅格底图上的聚合数量和序号提供文字渲染，地图样式加载公开字体
`https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf`。
**字体 URL 与 OSM 瓦片服务需要可用的网络连接**；若聚合圆点可见但数字缺失，
优先检查浏览器 F12 Network 里的字体请求状态。

### 本地验收（在项目根目录，先确认 Git 没有未提交冲突）

```powershell
git fetch origin
git switch -c feat/webgis-v1.3-map-interaction-20261015 --track origin/feat/webgis-v1.3-map-interaction-20261015
# 若本地已有该分支，改为 git switch feat/webgis-v1.3-map-interaction-20261015
node tests/frontend-workflow.mjs
node tests/ai-itinerary-ui.mjs
node tests/ui-layout.mjs
cd frontend
npm ci
npm run build
cd ..
# 分别用两个窗口继续运行：
.\start-backend.ps1
.\start-frontend.ps1
```

浏览器打开 http://localhost:5173。建议顺序：

1. 缩放 9–13：多个密集景点以**带数量的蓝色聚合圆点**显示，点击后放大；
   缩放到 14–16：恢复单 POI 点击详情；
2. 切换「点位/热力」：热力图仍基于原始 POI；切回点位聚合恢复；
3. 左侧选择景点：右侧详情自动打开、地图橙色环高亮，关闭详情后环消失；
4. 在详情里添加 3 个景点至「我的路线」：地图显示 1/2/3 蓝色数字、
   左侧显示「第 N 站」；移除中间站后数字按最新顺序重排；
5. 在「我的路线」中点击站点：地图定位对应点并跳转到详情；
6. 「AI 行程」标签：不用第二次点击展开即可看到输入项。
   无 Key 情况仍可本地规则生成；真实 DeepSeek 测试须用户主动配置本地 Key，
   可能消耗 API 额度；
7. 使用「附近 5km」「我的收藏」与任意类别过滤：不应出现旧聚合点残留，
   如地图 POI 列表 0 个，聚合源也应同步清空；
8. 在 Chrome DevTools 网络工具中检查 OSM 底图瓦片与文字 glyph 请求，
   验证 1600×900 桌面界面和缩窄浏览器时无功能面板遮挡。

`node tests/frontend-workflow.mjs` 包括聚合图层、点位/热力切换、
来源同步、聚合点展开、选中高亮和路线编号回归。
GitHub CI 是代码层验收，不等于 Windows 真实地图或字体 CDN 已实测。

**重要分支关系**：现有 `feat/poi-tourism-metadata-20261008`（含更多 AI 对话/
Valhalla / 入口数据）仍与本分支独立；避免在 v1.3 审核前盲目合并它们。


## v1.7 业务流程验收（开发分支）

本阶段优先验证“搜索 → 生成 → 预览确认 → 保存 → 恢复 → 导出”的状态边界。
GitHub Actions 运行所有 `tests/test_*.py` 后端离线单元测试，
及现有前端模拟交互与 Vue 构建。**模拟测试并非真实浏览器端到端测试**。

在 Windows 项目根目录运行：

```powershell
git fetch origin
git switch feat/v1.7-journey-acceptance-20261015
git pull --ff-only origin feat/v1.7-journey-acceptance-20261015
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
node tests/frontend-workflow.mjs
node tests/ai-itinerary-ui.mjs
node tests/ui-layout.mjs
cd frontend
npm ci
npm run build
cd ..
```

人工业务流程（启动 PostgreSQL、后端和前端后进行）：

1. 输入南京景点关键词搜索并打开详情；核实地图选中高亮和数据库 POI 名称一致。
2. 进入 AI 行程工作台，使用无 Key 规则回退生成路线，确认景点 ID 均来自数据库，地图提示直线非导航。
3. 展开推荐依据及质量诊断；确认规则分仅在规则排序时用于解释，类别多样性不宣称准确率。
4. 点击“减少景点并预览”，确认原地图未被预览替换；点击“确认替换当前行程”后才生效，重复确认不应重复应用。
5. 保存行程并刷新浏览器，恢复后检查站点顺序与当前数据库内容；断开后端测试失败时原地图不变。
6. 导出 JSON 和浏览器打印报告；无已验证 Valhalla 道路时，GeoJSON 道路导出按钮必须禁用。
7. 手动修改地图路线使原 AI 方案失效；未确认预览不得再覆盖当前路线。
8. 切换窄屏、点位/热力、景点列表/工作台，检查路线编号、地图图层和滚动布局。
9. 可选：仅用户主动配置私有 DeepSeek Key、VALHALLA_URL 并同意调用成本后，实测模型排序和真实道路服务，不得将公共服务成功率视为生产级保障。

所有真实 PostGIS、字体网络、Valhalla、浏览器打印以及交互截图仍需本机人工检查；CI 成功不代表它们自动通过。
