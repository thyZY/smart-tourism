# 玄武湖两处候选入口：原始OSM道路拓扑复核（2026-10-10）

**状态：研究证据已核对，入口尚未批准；不得修改 `routing_access` 为 `reviewed`。**

## 数据与方法

来自用户 Windows 本机 `--osm-api --save-osm-snapshots` 原生OSM JSON快照：

- `xuanwumen_west.json`：994 nodes、41 ways、7 relations；
- `jiefangmen_south.json`：1405 nodes、61 ways、8 relations；
- `xuanwu_lake_osm_audit_local(1).json`：核查生成时间 `2026-10-10T02:26:09Z`；
  两处候选点分别位于（WGS84估算）`118.78229935,32.07257793` 和
  `118.79144511,32.06429665`。

脚本旧筛选集包含 `barrier=gate` 及 `entrance=yes`，
但忽略 `barrier=entrance`、`barrier=sally_port` 和 `ref` 字段。
本轮从**完整原生JSON**重新建立Way节点引用和步行候选路网，纠正漏检。
所有路程是对应OSM几何线段的球面长度之和，不是Valhalla实时导航。

© OpenStreetMap contributors (ODbL)；保留OpenStreetMap元素URL。
来源地图标点仍是 GCJ-02→WGS84 **估算**位置。

## 玄武门：发现穿城墙通道及步行入口标签（未核准）

原审计：附近13条可步行Way，0个显式闸门。
原生节点包含两条被旧筛选规则漏掉的信息：

| OSM对象 | WGS84经度、纬度 | 标签及意义 |
|---|---|---|
| [node 9753621811](https://www.openstreetmap.org/node/9753621811) | 118.7824099、32.072635 | `barrier=sally_port`，同时在南京城墙Way和两条`highway=service`Way中，距高德估算标点约12.2m |
| [node 1111402644](https://www.openstreetmap.org/node/1111402644) | 118.7831195、32.0727504 | `barrier=entrance`、`foot=yes`、`bicycle=yes`，位于`highway=service` Way 239377731，距估算标点约79.6m |

历史城墙 / 城门Way： [940335843（玄武门建筑）](https://www.openstreetmap.org/way/940335843)、
[95918075（南京城墙）](https://www.openstreetmap.org/way/95918075)。

原生Way共享节点推导出的**候选道路图**：
`1111402644 → 1111402632 → 1038862146 → 9753621811 → 13875823214`
长度约 **95.8m**；包含
[239377731](https://www.openstreetmap.org/way/239377731)、
[1095550197](https://www.openstreetmap.org/way/1095550197)、
[280718320](https://www.openstreetmap.org/way/280718320)，
道路类型均为 `highway=service`，末端13875823214也属于
[1521272063（footway）](https://www.openstreetmap.org/way/1521272063)。

由此可以**确认OSM数据表达了穿过城墙sally_port位置、接上步道的候选拓扑**。
但是这些路段的 `highway=service` 与 `barrier=sally_port` 标签
**不足以证明游客当前被允许从这里通行**；`1111402644` 也不等于城墙上的
`sally_port`，不能互换坐标或自动批准。

## 解放门：应排除鸡鸣寺出口，优先调查共享步道节点

原审计：22条可步行Way、194段；最近高德标点的步道路段
[1061607201](https://www.openstreetmap.org/way/1061607201) 距约**2.3m**。

此前唯一计数为入口的
[node 12325223492](https://www.openstreetmap.org/node/12325223492)：
- `entrance=yes`，但完整原生标签另含 **`ref=鸡鸣寺出门`**；
- WGS84`118.790473,32.063818`，距高德估算标点约**105.9m**；
- 在`highway=unclassified` Way 1332131601，不属于已筛选的步行Way；
- 最近可步行Way线段约**43.4m**。

**结论：这是鸡鸣寺出口标注，不能按“玄武湖解放门”入口使用。**

与解放门地标更直接相关的证据：
- 步行共享[node 2929152731](https://www.openstreetmap.org/node/2929152731)
  约`118.7914745,32.0642819`，距转换后高德标点约**3.2m**；
  同时属于[280725993](https://www.openstreetmap.org/way/280725993)、
  [479232950](https://www.openstreetmap.org/way/479232950)、
  [1061607201](https://www.openstreetmap.org/way/1061607201)三条footway；
- OSM附近还包含`information=office`、`name=解放门`的
  [node 6635347293](https://www.openstreetmap.org/node/6635347293)，
  离候选标点约11m，但**咨询点也不能视为入口通行节点**；
- [1061610836](https://www.openstreetmap.org/way/1061610836)记为
  `historic=city_gate`、`name=解放门`，是门址地标而非已批准导航点。

在只允许 OSM `footway/pedestrian/path/living_street` 步行图、
并允许 `steps` 时：从 `2929152731` 到选定
[环湖路Way 290148744](https://www.openstreetmap.org/way/290148744)
上的节点 `1111383721`，最短长度约 **197.5m**，
途中经过[89637348（steps）](https://www.openstreetmap.org/way/89637348)；
排除所有`steps`后，同两节点最短路约 **493.0m**。
这只能说明**局部OSM节点连通关系及台阶影响**，
并非已证明可进公园、无障碍可达或不跨门禁的真实道路。

## 安全处理与下一次验收

本次已调整 `scripts/audit_xuanwu_osm.py`：
1. 增加 `barrier=entrance`、`barrier=sally_port` 候选；
2. 保留节点`ref`、`foot`、`bicycle`标签与所在道路Way引用，
   并标记可能属于其他景点的入口（鸡鸣寺出口）；
3. 每项仍为 `candidate_requires_manual_review`，不得当作导航点。

人工QGIS复核重点：玄武门 `9753621811` 是否是当前实际可穿越
的园区门道（`1111402644` 是不同位置）；解放门步道
`2929152731` 附近是否确实从公共街道通往园内，注意台阶、城墙、售票点
及入口管控。如果仅有OSM几何连通，没有可靠入园权限信息，
仍应维持所有 `routing_access` 为NULL/draft。

**尚未执行**PostGIS更新、Valhalla A/B实测、游客入口的人工批准。
