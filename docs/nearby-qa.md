# Nearby 修复验收（2026-09-07）

## 根因证据

原代码在“博物”搜索完成后定位到 zoom 14，Nearby 仅 setData，没有调整视野。
浏览器运行时检查：source.type 为 geojson，source 内包含南京博物院、夫子庙，
places-points 是正常的 circle layer，无 filter 或隐藏配置。
1034×637 视口下南边界纬度为 32.029112838，夫子庙纬度为 32.027，
`queryRenderedFeatures` 仅返回南京博物院。说明 source 更新成功，第二个点在屏幕外。
最小 fitBounds 修复后，实际浏览器截图确认两个红点可见，再完成其余 P0。

另有潜在初始化竞争：旧代码首次 axios 返回后才 addSource，此前查询会静默跳过
setData。新代码先创建空 GeoJSON source/layer，再开放查询；所有请求共用 loading。
未发现定时覆盖、style 切换、图层过滤逻辑；不能把初始化竞争冒充本次已复现根因。

## 验证结果

- 真实 API：全部 3 个；博物 1 个；不存在 0 个。
- 固定博物院中心 Nearby：南京博物院 0.00 km，夫子庙 1.57 km，无中山陵。
- (0,0) Nearby：0 个。
- 实际浏览器 A–F：默认三个红点；搜索自动 Popup；Nearby 两个红点且旧 Popup
  清除；点击夫子庙显示 1.57 km；无结果清空并返回概览；清空搜索恢复三个红点。
- 再次普通搜索正确显示无距离 Popup；验收页面 error/warn 日志为空。
- `node tests/frontend-workflow.mjs`：初始化锁、重复请求、三条网络失败路径、
  空 Nearby、恢复请求、卸载取消及迟到响应保护通过。网络故障采用受控替身验证，
  没有停止用户正在运行的后端服务。
- `tests/verify_database.py`：独立 schema 内创建新 places，两次执行 schema/seed，
  均为三个 UTF8 中文 POI，SRID 4326 和 GiST 索引正确；整个事务回滚。
  测试通过 psycopg2 执行 SQL，核对并移除 psql 专用编码指令后设置客户端 UTF8；
  本次未另开全新数据库或重新执行 Windows psql CLI。
- `npm run build`、`git diff --check`、两个 PowerShell 启动脚本语法检查通过。

## 边界

构建仍提示 MapLibre 主包超过 500 kB；不影响本次功能。现有 geometry GiST
不直接加速 geography 表达式查询，规模扩大后需实际 EXPLAIN 再决定索引。
地图初次就绪依赖 OSM 瓦片加载；本次保留原底图。Demo 坐标按用户既有 seed 保留，
未做现实位置校准。启动脚本未以重启整机方式验证。
