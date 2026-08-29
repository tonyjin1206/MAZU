# Mazu Trade System (MTS)

> **v2.8.0** — Mazu Trade System — A Lightweight Trade Management Platform  
> 采购 · 销售 · 生产 · 库存 · 财务 · 退税 — 全链路数字化  
> **支持 AI 智能助手对话式操作**  
> v2.6.0 新增**销售退货财务层**：发票红冲 · 红字应收 · 退款 · 核销转移 · 退货联动 · 负数申报  
> v2.7.0 新增**预警提醒系统**：通知铃铛 · 事件埋点 · 规则配置 · 应收/应付账期预警  
> v2.8.0 重构**销售订单三分支**：转直采 · 转外发 · 转生产-自产；生产模块去委外化（纯自产），委外归口转外发

---

## 快速开始

```bash
# macOS / Linux
chmod +x install.sh && ./install.sh

# 或者使用跨平台启动器（macOS / Windows / Linux 通用）
python launcher.py
```

启动后自动打开：
| 地址 | 说明 |
|------|------|
| `http://localhost:5173` | 前端系统界面 |
| `http://localhost:8788` | 后端 API |

**默认账户：** `admin` / `admin123`

### Windows 手动启动

> 💡 推荐使用仓库根目录的开发脚本（自动清除 `PYTHONPATH`，避免 Hermes 等其他环境的
> site-packages 抢占项目依赖版本）：

```bash
# 终端 1：启动后端（清 PYTHONPATH + 开发热重载）
./dev.sh        # git-bash；Windows 资源管理器可直接双击 dev.bat

# 终端 2：启动前端
cd frontend
npm run dev
```

手动等效方式：

```powershell
# 终端 1：启动后端
cd backend
venv\Scripts\activate
python run.py

# 终端 2：启动前端
cd frontend
npm run dev
```

### 跨平台启动器（推荐）

```bash
# 安装依赖（首次运行）
python launcher.py install

# 启动服务
python launcher.py start

# 一键安装 + 启动
python launcher.py

# 重置数据库
python launcher.py reset-db

# 查看帮助
python launcher.py --help
```

> ⏱ 首次安装约需 3-5 分钟（取决于网络速度）

---

## 系统要求

| 组件 | 最低版本 |
|------|---------|
| 操作系统 | macOS 12+ / Windows 10+ / Linux |
| Python | 3.10 或更高 |
| Node.js | 18 或更高 |
| 内存 | 4GB 以上 |
| 磁盘 | 500MB 可用空间 |

---

## 功能模块

```
基础档案 → 客户 / 供应商 / 物料 / 产品 / BOM / 工序 / HS编码 / 币种汇率（自动获取+手工维护）/ 仓库维护
采购管理 → 销售订单转采购 / 采购订单（含成品采购）→ 采购入库 → 采购发票 → 应付账款 → 付款
销售管理 → 销售订单（审核后明细行三路分流：转直采/转外发/转生产-自产）→ 销售发货（两步化）→ 销售发票 → 应收账款 → 收款
生产管理 → 生产订单（纯自产，去委外化）→ 派产 → 发料 → 完工 → 成品入库 / 外购直采推采购需求
委外管理 → 销售订单转委外 → 委外订单（分工序/供料方式/认领原料）→ 加工费发票
库存管理 → 收发存报表 / 库存流水 / 批次追溯 / 成品入库 / 原料入库 / 原料出库 / 成品出库 / 盘点（独立菜单·盘盈盘亏）/ 采购红冲 / 销售退货
退税申报 → 申报期管理 / 发票关联 / 状态跟踪
AI 助手 → 右下角悬浮球随时对话 / 档案与库存查询 / 创建与审核单据 / 收付款 / 发票录入 / 发料入库 / 操作手册问答（按菜单权限控制，全程留痕）
管理驾驶舱 → 现金收支 / 应收应付账龄 / 销售毛利分析（支持穿透查询）
```

---

## 技术栈

```
后端：Python FastAPI + SQLAlchemy + SQLite
前端：Vue 3 + Vite + Element Plus
认证：JWT Token
部署：前后端分离，零配置启动
```

---

## 文档

| 文档 | 说明 |
|------|------|
| `docs/product-overview.md` | 产品功能概述（v2.8.0 三分支流程） |
| `docs/operations-manual.md` | 用户操作手册（含场景举例，v2.8.0 三分支） |
| `docs/one-pager.html` | 赛博朋克风格产品宣传页 |
| `docs/test-report-1.md` | 自动化测试报告（阶段 0-5 最终版） |

---

## 自动化测试

```bash
# 后端全套（契约/状态机/边界/全流程/收发存v2/三分支，259 个用例）
# 推荐：自动清除 PYTHONPATH（防依赖污染），支持透传 pytest 参数
./test.sh                     # git-bash / macOS / Linux；Windows 可双击 test.bat
./test.sh -k 汇率             # 例：按关键字过滤

# 等效手动命令：
cd backend && env -u PYTHONPATH ERP_DEV=1 venv/Scripts/python.exe -m pytest tests/ -q

# 架构检查（废弃表/散写 request/弃用 API）
python scripts/check_architecture.py

# E2E（32 页面冒烟 + 核心业务流程，自动起独立服务）
cd e2e && ERP_DEV=1 python -m pytest -q

# CI：.github/workflows/ci.yml 三 job（后端 + 前端构建 + E2E）
```

### 测试数据规范（重要，新增测试必须遵守）

**统一数据构建器：`backend/tests/test_data.py`**

1. **所有测试共用一套基础档案构建**：`build_foundation(client, headers)` 通过 API 创建全套真实档案
   （2 仓库 / 2 供应商 / 2 客户 / 4 物料 / 2 产品 / 4 工序 + BOM + 工艺路线），
   共享 fixture 为 `foundation`（conftest.py，session 级）。
2. **禁止在各自测试文件里另建基础档案**（历史教训：各文件独立建仓库导致
   RM990001 / WH-BND / WH-BOT 等垃圾数据堆积、仓库字段不全、数据量失控）。
   新测试需要新档案 → 在 `test_data.py` 的 `build_foundation` 上扩展。
3. **仓库档案必须字段完整**（code/name/wh_type/address/manager）—— 后端出入库/盘点
   接口会对 `warehouse_id` 做仓库档案参照校验（不存在或停用 → 400），
   测试数据必须走真实档案创建，禁止直接灌 SQL。
4. **数据少而真实**：纺织真实业务数据（棉纱/坯布/印染），单个流程测试 1~2 个订单，
   不搞批量刷数。
5. 单元式测试（如库存 v2 的 6 个场景）允许独立小数据集（保证隔离），
   但必须复用 `test_data.py` 的真实数据风格与完整字段，禁止自造垃圾 code。

**测试库注意**：pytest 复用 `backend/data/erp.db`（同一数据库），每次运行前自动清空业务表并重建种子。
跑完测试后如需干净开发库，执行 `python scripts/reset_local_db.py`（白名单保留系统表）。
