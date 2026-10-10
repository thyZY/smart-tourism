# 玄武湖 OSM 原生数据：首次本机审计记录（2026-10-10）

## 范围、来源与限制

由用户在 Windows / PowerShell 本机执行：
`python scripts/audit_xuanwu_osm.py --osm-api`。分析的是
`https://api.openstreetmap.org/api/0.6/map.json` 两处约180 m候选点周边
OSM节点、步行路段（© OpenStreetMap contributors / ODbL）。
生成UTC时间：`2026-10-10T02:08:37.108185+00:00`。

原始完整研究输出保存在用户本机
`data/entrance_evidence/xuanwu_lake_osm_audit_local.json`，
本报告只复述与入口判断有关的少量事实，不代表实地核查或交通安全验证。
未经审查的报告文件不会自动作为正式 `routing_access` 数据提交。

## 两处候选的事实结论

| 内容 | 玄武门 | 解放门 |
|---|---|---|
| GCJ-02→WGS84转换后的候选高德标点（经度、纬度） | 118.78229935, 32.07257793 | 118.79144511, 32.06429665 |
| 原生OSM数据中脚本筛选出的可步行way数 | 13 | 22 |
| 180米范围内明确标记 `entrance` / `barrier=gate` 的节点数 | 0 | 1 |
| 标记节点是否属于已检出的可步行way节点序列 | 无显式节点 | **否** |
| 是否有资料足以设置 `reviewed` | **否** | **否** |

### 解放门单个OSM入口节点

- OSM Node ID：`12325223492`；
  https://www.openstreetmap.org/node/12325223492
- 经纬度（OSM/WGS84）：`118.790473, 32.063818`。
- OSM标签仅有 `entrance=yes`；没有明确记载禁止步行的标签，
  **但标签缺失不等于明确允许步行**。
- 与高德原始标点逆转换结果相距约 **105.9米**。
- 到最近可步行OSM **节点** 的距离约 **43.4米**；
  注意这**不是到步道路段的最近距离**。
- `pedestrian_way_membership_ids=[]`，
  `is_member_of_walkable_osm_way=false`。
  不能据此肯定它与园区入口、步行网络相连，甚至不能独立证明此节点
  就是原先高德地图中的“解放门”入口。
- 审核状态：`candidate_requires_manual_review`。

### 玄武门

已有13条脚本认可的步行way，但180米范围内无显式
`entrance` / `barrier=gate` 候选节点。
这**不证明**玄武门关闭、不存在或不可进入，
只能说明附近OSM闸门标签不充分。

## 后续应收集的具体证据

1. 新版 `scripts/audit_xuanwu_osm.py` 会计算**闸门→步道路段**
   的投影最短距离，同时报告**高德转换点→附近路段**
   的候选way URL与最近线段端点ID。请不要把旧版43.4米节点距离
   与新版线段距离混作同一种指标。
2. 本机使用 `--osm-api --save-osm-snapshots` 生成两处原生OSM JSON快照，
   让QGIS/OSM查验实际通路、路口及是否有断开的路径；
   快照默认不提交到GitHub。
3. 用地形/OSM步道、景区公告和可辨认的开放入口位置逐个确认，
   不把带有 `entrance=yes` 但游步道没有连接的点当作已验证入口。
4. 在确定人行通道允许穿行并审核来源后，才考虑在用户知情下
   录入一条 `routing_access.pedestrian` 的 `reviewed` 记录，
   并对比Valhalla旧/新道路；**不启用机动车入口**。

**当前结论：无可直接升级的正式审核入口；原40个POI和道路计算继续回退原始坐标。**
