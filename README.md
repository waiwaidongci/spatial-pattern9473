# 陇格空间聚集观察席

对匿名网格均值与明确的邻接图做全局Moran I、局部条件置换及全部格点BH校正，把探索线索交给独立补测。

陇格公共步行研究组有18位空间分析员，研究步行区域的匿名噪声暴露汇总。上游 `lg-walk-noise-202611-grid.csv` 按250m格边汇总均值dBA；以前在表格和GIS里手工涂热图，容易把相邻深色当成显著、忽略rook邻接与边界、逐点挑p导致误报。本系统替代聚集筛选与审阅归档环节，下游由负责人批准独立补测方案，阅读者下载带q值与口径指纹的CSV。当前数据为具名团队的固定种子合成研究环境，不含真实个人或地理定位。

## 快速启动

```sh
cp .env.example .env
docker compose config --quiet
docker compose up -d --build
docker compose exec -T backend python -m scripts.seed_demo
```

可在含中文、空格的项目目录启动。前端 http://localhost:18226 ，API文档 http://localhost:19226/docs ，PostgreSQL localhost:17726。恰好5服务：Nginx前端、FastAPI、独立Python worker、PostgreSQL16、Redis7。全部有健康检查；backend/worker等待数据库与Redis，frontend等待backend。Redis存队列，数据库存快照与结果，共享命名产物卷保存完整结果JSON。Nginx把 `/api/` 去前缀代理到后端，无重复前缀。

| 角色 | 账号 | 密码 | 页面与典型动作 |
|---|---|---|---|
| admin 测绘负责人 | admin@longge.demo | Longge2026! | 六页；创建研究、批注、提交、批准/退回补测方案 |
| analyst 空间研究员 | analyst@longge.demo | Longge2026! | 六页；核对图、创建置换研究、批注、提交补测说明 |
| viewer 补测阅读者 | viewer@longge.demo | Longge2026! | 六页只读；下载获批完成研究CSV |

JWT角色在后端执行，阅读者不能写入，研究员不能审批。未批准研究不能导出，已审阅建议不能重复审批。登录/批注/创建/worker完成/建议及审批写审计；登录IP每分钟最多30次，另有统一错误处理中间件。本机演示配置部署前需修改JWT_SECRET及Compose内数据库口令。

## 一天的剧本

1. 09:00 陆禾以研究员登录，核对 `LG-01`“一期 · 聚集暴露观察”，64格、112条无向rook边，250m格边。
2. 09:05 在“网格与邻接”打开rook连线，点选 `G01-01`，确认角格2邻居、边格3、内部格4；给该格记录独立时段补测批注。
3. 09:10 查看 `LG-03` 恒定62dBA边界，系统拒绝未定义Moran统计量；不把常量热图说成无聚集证据。
4. 09:15 为 `LG-01` 新建“499次聚集研究”，B=499、根种子2026。创建时冻结期、格点、边与批注快照。
5. 09:16 worker真实读取Redis任务，计算全局标签置换、每格固定自身的条件置换，再对全部64格BH校正。
6. 09:20 查看全局I约0.73683757、双侧p=.002、q≤.05为7/64（来自真实seed/HTTP运行），再点开局部I、条件期望、符号象限与q。
7. 09:25 写“边界格独立补测”建议：保持250m匿名尺度，针对探索筛选格及邻接边界另选时段；不推断点位原因。
8. 10:00 秦榆批准研究归档；徐原以阅读者下载 `spatial-run-N.csv`，开展独立补测。批准不构成噪声标准判定或行动效果保证。

## 六页与五实体

观察总览、网格与邻接、置换配置、聚集证据、补测审阅、研究留痕。`SpatialSurvey / GridCell / NeighborEdge / SpatialRun / SamplingNote` 均贯穿数据库表、model、schema、service、route、前端API、store与页面/组件；另有User/Audit。来源期/数值/边只读核对，格点批注可写，已创建运行使用冻结快照。

seed三期各8×8=64格，共192格、336条无向rook边（每期112）。`LG-01`含高低块状均值、`LG-02`随机均值、`LG-03`常量边界。生成种子220/221/222，仅作匿名合成研究。自然键为用户email、观测期code、(期,格code)、(期,a,b)及基线运行name；重复seed只补缺失，不新增重复或覆盖用户批注/建议。`SEED_DEMO=true`启动自动执行一次，失败仅记日志，独立seed仍可执行。

`RunSummary`在首页、结果、审阅复用，`GridMap`在首页、来源、结果复用，此外有SurveySelector、MoranScatter、PermutationPlot及通用DataTable/Notice/StatusBadge。图、散点、零分布、明细全部来自后端数据，前端只负责映射显示。

## 统计口径

输入无向简单图，至少4格且不超过100格；拒绝自环、未知端点、重复无向边和孤点。种子图为共享边rook；每条边只存一次，计算时双向展开，二元邻接每行除以邻居数得到W。原图无向不意味着行标准化后W仍对称；S₀=Σwᵢⱼ=n。

令zᵢ=xᵢ−平均值，m₂=Σzᵢ²/n：

```text
global I = (n/S₀) ΣᵢΣⱼ wᵢⱼ zᵢzⱼ / Σᵢ zᵢ²
local Iᵢ = zᵢ Σⱼ wᵢⱼzⱼ / m₂
E[global I] = −1/(n−1)
E[local Iᵢ | zᵢ] = −zᵢ² / ((n−1)m₂)
```

数值计算先减去首值，再除以最大绝对差并中心化，避免对可分辨的小方差使用绝对阈值。统计量对平移与正比例不变；仅当输入真实恒定或在浮点精度下不可分辨时拒绝。数值要求有限、绝对值≤1e9。页面散点采用中心化标准分数z与lag(z)，公式等价。

全局每次均匀置换所有格标签，双侧围绕E而非0：`p=(1+#(|I*−E|≥|Iobs−E|))/(B+1)`。局部固定自身zᵢ，从其余n−1标签中无放回抽取k个邻居（k为该格度数），以均匀行权重重算Iᵢ，双侧围绕各自条件期望；禁止把自身也放进候选池。极端比较使用64倍机器epsilon乘统计量尺度的浮点并列容差（不是方差拒绝阈值）。B=499–999，格数×B≤64000；p分辨率1/(B+1)，Monte Carlo有抽样误差。

BH把全部有效格的p排序，计算 `q_(i)=min_{j≥i}(m p_(j)/j,1)`，不先挑格再校正。q≤.05仅作探索筛选；空间依赖下标准BH的FDR保证不普遍成立。HH/LL为同向、HL/LH为异向、AXIS为零轴，均是符号象限，不能单独当作显著聚集。

根SeedSequence按格code稳定排序，为全局与各局部检验派生独立子流。保存全部全局/局部置换零分布、极端计数、期望与分辨率；页面直方图只展示全局分箱，API/产物保留完整明细。SHA256覆盖算法版本、完整期/格数值/位置/批注、标准化无向边、B与seed，输入行序/边朝向变化不改指纹；有效内容改变会变。局部均值等于全局I是行标准化S₀=n时的内部恒等式，另有独立四节点与全枚举oracle。

全局交换性与局部条件交换性需要研究设计支持。趋势、尺度、邻接选择、边界及未观测混杂会影响解释；本系统描述关联，不能推断因果、直接证明点位成因或保证补测行动效果。

## 开发与工程

技术栈：React18.3/ReactRouter7.18.5/TypeScript5.7/Vite6.4，Python3.11/FastAPI0.115/SQLAlchemy2/NumPy2.2，PostgreSQL16/Redis7/Nginx1.27。后端真算全部统计量，worker执行任务，API提供快照/审阅与权限。

```sh
# backend，先准备可连接的PostgreSQL/Redis并设置DATABASE_URL、REDIS_URL
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
# 另开终端在backend启动worker；本地需可写/artifacts，推荐Compose
python -m src.worker
# 前端在项目根进入frontend；Vite代理/api到localhost:8000
cd ../frontend
npm ci
npm run dev
```

`backend/src/{routes,controllers,services,models,schemas,middlewares,utils,constants,config}` 按来源/图/统计/运行/建议/横切职责拆分；`backend/scripts/seed_demo.py`；`backend/migrations/001_initial.sql`为可选索引升级，首次schema由SQLAlchemy metadata创建，不是独立全量DDL。`frontend/src/{api,stores,types,components/common,hooks,pages,router,utils,constants}` 为React应用。

`.env`参数 COMPOSE_PROJECT_NAME、FRONTEND_PORT、BACKEND_PORT、DB_PORT、JWT_SECRET、SEED_DEMO；数据库与Redis连接由Compose定义DATABASE_URL/REDIS_URL。角色枚举在`backend/src/constants/roles.py`与`frontend/src/constants/enums.ts`，被后端路由鉴权和前端角色显示使用；运行状态在`backend/src/constants/status.py`与同一前端enums，被worker及StatusBadge使用；审阅状态在`backend/src/schemas/note.py` Literal、model/service及前端ReviewStatus。

测试与截图在同批 `test-artifacts/gb-0022/`，关键JSON/CSV直接保留在证据根，原始build/teardown日志在logs。已知差异见TESTING。单worker无崩溃任务恢复/多worker去重、来源上传、真实GIS定位或设备连接；不执行外发邮件或真实补测。清理本题：`docker compose down -v --remove-orphans`。MIT License。
