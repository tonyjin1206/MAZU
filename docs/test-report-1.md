# MTS 外贸ERP 自动化测试报告（最终版）

> 范围：阶段 0-5 全部完成（契约测试 / 状态机 / 边界数据 / 架构检查 / E2E）。
> 日期：2026-07-31 · 分支：app-optimization

---

## 一、执行结果汇总

| 测试层 | 文件 | 结果 | 说明 |
|---|---|---|---|
| 契约测试（前后端匹配） | backend/tests/test_contract.py | ✅ 2 passed | 前端全部调用链 vs 后端路由，0 缺口 |
| 状态机测试（设计逻辑） | backend/tests/test_state_machine.py | ✅ 110 passed | 4 单据 × 全部状态 × 全部操作矩阵 |
| 边界数据测试（离谱输入） | backend/tests/test_boundary.py | ✅ 39 passed | 37 种离谱输入无 5xx + RBAC 越权 403 |
| 历史全流程（回归） | backend/tests/test_textile_flow.py | ✅ 通过 | 含逆向操作 + 备货方式确认 |
| 基础档案/数据/RBAC | backend/tests/ | ✅ 通过 | 已更新适配当前 API |
| 架构检查 | scripts/check_architecture.py | ✅ PASS | 0 违规（废弃表/散写/弃用 API 全清） |
| **后端总计** | | **187 passed / 0 failed / 0 skipped** | |
| E2E 冒烟（页面打开） | e2e/test_smoke_pages.py | ✅ 33 passed | 32 页面 + 登录页，0 console/页面/网络错误 |
| E2E 核心流程（真实操作） | e2e/test_core_flow.py | ✅ 1 passed | 建档→销售→审核→生产 全链路 |
| **E2E 总计** | | **34 passed** | Chromium headless，独立测试库 |

---

## 二、测试过程中发现并修复的问题（7 项）

| # | 问题 | 严重度 | 修复 |
|---|---|---|---|
| BUG#1 | 采购入库必 500（product_id 传给无此字段的模型 + material_id NOT NULL 挡成品） | 🔴 严重 | 模型加 product_id 列、material_id 可空、delete_receipt 双路径回滚、迁移脚本 |
| #14 | GET /auth/users 等 4 接口只认证不授权 | 🟡 | require_permission("menu:system:users") |
| 委外残留 | Outsourcings.vue 打开即报错（后端无路由）+ mo_outsourcing 等表 | 🟡 | 删页面/API/模型/表/AI 工具 create_outsourcing（9→8 工具） |
| #4 | 12 个"定义了但后端没有"的 API | 🟡 | crudApi 方法子集对齐，删 departments/employees |
| #5 | 17 页面 109 处散写 request（契约测试盲区） | 🟡 | 97 处迁移到 api/*.js 封装，散写清零 |
| #6 | 46 处 Pydantic class Config 弃用 | 🟢 | model_config = ConfigDict |
| 盘点表 | inv_stock_check 等 2 个未开发功能表 | 🟢 | 删模型 + DROP 表 |

## 三、E2E 架构

```
e2e/conftest.py
├── services fixture: 独立后端(8789, ERP_DATA_DIR=临时库) + 前端(5174, VITE_PROXY_TARGET)
├── browser fixture: Chromium headless
├── page fixture: 每测试独立上下文 + 三类错误收集(console/pageerror/4xx-5xx)
└── logged_in fixture: 真实登录 admin

e2e/test_smoke_pages.py   32 个页面逐个打开，断言 0 错误
e2e/test_core_flow.py     客户→产品→销售订单→审核→生产订单 全 UI 操作
```

运行方式：`cd e2e && ERP_DEV=1 python -m pytest`（自动起服务、自动清理）

## 四、CI 持续集成（已接入）

`.github/workflows/ci.yml` — 3 个 job（push/PR 到 main 或 app-optimization 触发）：

| Job | 内容 | 耗时参考 |
|---|---|---|
| backend-test | flake8 + 187 个 pytest + 架构检查 | ~2min |
| frontend-build | npm ci + vite build | ~2min |
| e2e | Chromium + 独立测试库 + 34 个 E2E 测试（自动起服务） | ~3min |

## 五、遗留（用户可后续决定）

- E2E 覆盖核心流程 1 条链路，可扩展更多业务场景（采购→入库→发货→收款→退税）

