# 任务简报：基于代码重写全套项目文档

## 目标
你是一个高级技术文档工程师。请完整阅读本项目代码库，基于**代码实际实现**（而非已有文档）重新编写以下5份文档，输出到 `docs/claude-written/` 目录：

1. **01-产品文档.md** — 产品功能说明书（面向产品经理/客户）
2. **02-项目文档.md** — 项目技术总览（面向技术管理者/新加入开发者）
3. **03-开发文档.md** — 开发者指南（面向接手开发的工程师）
4. **04-操作手册.md** — 业务操作手册（面向终端业务人员）
5. **05-营销一页纸.md** — 营销一页纸（面向潜在客户/投资人）

## 阅读顺序（必须按此顺序）

### 第一步：理解全局
- `README.md` — 项目概览
- `PROJECT.md` — 项目文档（参考用，以代码为准）
- `CHANGELOG.md` — 版本历史
- `backend/app/main.py` — 后端入口，理解所有路由挂载
- `backend/app/models.py` — 数据模型全貌
- `frontend/src/router/index.js` — 前端路由/菜单结构

### 第二步：逐模块深入（后端 routers + 前端 views 对照读）
按以下顺序，每个模块读 router + 对应 views + 关键 model：

1. **基础档案** `routers/foundation.py` + `views/foundation/*.vue`
2. **销售管理** `routers/sales.py` + `views/sales/*.vue`
3. **采购管理** `routers/purchase.py` + `views/purchase/*.vue`
4. **生产管理** `routers/production.py` + `views/production/*.vue`
5. **委外管理** `routers/outsource.py` + `views/outsource/*.vue`
6. **库存管理** `routers/inventory.py` + `views/inventory/*.vue`
7. **退税管理** `routers/tax_refund.py` + `views/taxRefund/*.vue`
8. **系统管理** `routers/auth.py`, `routers/system_config.py`, `routers/notification.py` + `views/system/*.vue`
9. **仪表盘** `routers/dashboard.py` + `views/Dashboard.vue`
10. **AI 助手** `routers/bot_chat.py` + `components/MatsuAssistant.vue`

### 第三步：辅助文件
- `backend/app/schemas.py` — API 请求/响应结构
- `backend/app/utils/` — 工具函数
- `frontend/src/api/request.js` — API 封装
- `frontend/src/components/Layout.vue` — 菜单结构
- `docs/known-issues.md` — 已知问题

## 各文档要求

### 01-产品文档.md
- 产品名称：Mazu Trade System (MTS)
- 版本：v2.8.0
- 定位：轻量级外贸企业管理平台
- 内容：产品愿景、目标用户、核心功能模块详述（每个模块列出功能点、业务价值）、技术亮点（AI助手、三路分流等）、版本演进摘要
- 风格：专业但易读，避免代码，用业务语言

### 02-项目文档.md
- 技术架构（前后端分离、SQLite、JWT认证）
- 模块划分与职责
- 数据库表结构概览（列出所有表及核心字段）
- API 设计规范（RESTful 风格、路由前缀约定）
- 认证与权限体系（RBAC）
- 第三方集成（AI引擎、飞书等）
- 部署方案
- 目录结构说明

### 03-开发文档.md
- 开发环境搭建（Python/Node版本、依赖安装、启动命令）
- 项目目录结构详解
- 后端开发规范（路由注册、Schema定义、数据库迁移）
- 前端开发规范（组件结构、API调用、路由配置）
- 数据库设计（核心表ER关系、字段命名规范）
- API 接口文档（每个模块的主要接口，含请求/响应示例）
- 测试指南（pytest、测试数据、运行方式）
- 已知技术债务

### 04-操作手册.md
- 面向不懂技术的业务人员
- 系统登录
- 基础数据录入流程（客户/供应商/产品/BOM/工序/HS编码）
- 销售全流程（报价→订单→审核→发货→开票→收款）
- 采购全流程（需求→订单→入库→开票→付款）
- 生产全流程（订单转生产→排产→领料→生产→完工入库）
- 委外流程
- 库存管理操作
- 退税申报操作
- 常见问题FAQ
- 每个流程配操作步骤说明，关键字段解释

### 05-营销一页纸.md
- 一页纸格式（单页，信息密度高）
- 核心卖点（3-5个）
- 功能矩阵（模块×能力表格）
- 技术优势
- 客户价值（降本增效数据）
- 差异化竞争优势
- 号召行动
- 风格：简洁有力，适合打印或演示

## 重要约束
1. **以代码为准**：已有文档可能过时，一切以你读到的代码实际实现为准
2. **准确性第一**：不确定的不要写，宁可留空标注`[待确认]`
3. **中文输出**：所有文档用中文编写
4. **Markdown格式**：标准 Markdown，表格用管道语法
5. **每个文件独立完整**：不依赖其他文件即可阅读
6. **写完所有5个文件后，输出一个完成摘要**：列出每个文件的路径和字数
