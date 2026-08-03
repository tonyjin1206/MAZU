# Mazu Trade System (MTS)

> **v2.5.1** — Mazu Trade System — A Lightweight Trade Management Platform  
> 采购 · 销售 · 生产 · 库存 · 财务 · 退税 — 全链路数字化  
> **支持 AI 智能助手对话式操作**

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

# 重置数据库（清空全部业务数据，保留系统配置；需先停服务）
python launcher.py reset-db

# 一键重置 + 录入完整演示数据（纺织全流程 + 退货红冲演示，后端自动启动并保持运行）
python launcher.py init-db

# 查看帮助
python launcher.py --help
```

> **数据重置与初始化（手动两步）**：
> ```bash
> # 1. 清库（保留 admin/权限/系统配置，需先停后端）
> echo y | python scripts/reset_local_db.py backend/data/erp.db
> # 2. 启动后端后录入完整数据（纺织档案 + 全业务流程单据 + 退货红冲演示）
> python scripts/init_all.py
> ```
> `init_all.py` 数据源复用 `backend/tests/test_data.py` 的纺织真实数据（与 pytest 测试单一数据源），
> 流程：基础档案 → 销售订单→生产（备货方式/BOM/派产）→采购→入库→领料→完工→成品入库
> → 发货→开票→收款 → 报关→退税申报，末尾演示退货+发票全额红冲+退款。

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
采购管理 → 采购需求（外购转单）/ 采购订单（含成品采购）→ 采购入库 → 采购发票 → 应付账款 → 付款
销售管理 → 销售订单 → 销售发货 → 销售发票 → 应收账款 → 收款
生产管理 → 生产订单（自产/委外/外购备货方式）→ 派产 → 发料 → 完工 → 成品入库 / 委外 / 加工费发票 / 外购直采推采购需求
库存管理 → 收发存报表 / 库存流水 / 批次追溯 / 盘点（独立菜单·盘盈盘亏）/ 采购红冲 / 销售退货 / 出入库仓库参照校验
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
| `docs/product-overview.md` | 产品功能概述 |
| `docs/operations-manual.md` | 用户操作手册（含场景举例） |
| `docs/one-pager.html` | 赛博朋克风格产品宣传页 |
| `docs/test-report-1.md` | 自动化测试报告（阶段 0-5 最终版） |

---

## 自动化测试

```bash
# 后端全套（契约/状态机/边界/全流程/收发存v2，213 个用例）
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

**测试库隔离（强制规范）**：

| | 开发/生产库 | 测试库 |
|---|---|---|
| 位置 | `backend/data/erp.db`（config.py 默认） | `ERP_DATA_DIR` 指向的独立临时目录 |
| 数据 | 手工录入 + seed 脚本的真实业务数据 | `test_data.py` 构建的纺织测试档案 |
| 维护 | 手动维护，`scripts/reset_local_db.py` 显式重置 | 每次 pytest 自动清空重建 + 种子 |
| 被谁操作 | 后端服务 / 手工 / 迁移脚本 | 仅 pytest（conftest.py 的 setup_db） |

1. **测试绝不触碰开发库**：`backend/tests/conftest.py` 在导入 app 前设置
   `ERP_DATA_DIR=<临时目录>`（config.py 通过该环境变量决定数据目录），
   pytest 的 setup_db 清空/重建的只是测试库。跑完测试开发库数据（含 AI 配置
   `sys_bot_config`、手工档案）必须保持完全不变——验证方法：跑测试前后
   对比 `backend/data/erp.db` 的 mtime 与数据量。
2. **禁止在测试里绕过隔离**：不得直接改 `backend/data/erp.db`，不得手动
   指定 `ERP_DATA_DIR` 指向开发目录，不得用 `scripts/reset_local_db.py`
   当测试前置（那是开发库工具）。
3. **AI 配置属于开发库数据**：DeepSeek API Key 存在 `sys_bot_config`，
   一旦测试误清开发库，AI 助手会报「AI 未配置」——隔离规范就是为了防这个。
