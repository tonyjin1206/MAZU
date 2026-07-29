# MTS (Mazu Trade System) — 项目文档

## 概览

> A Lightweight Trade Management Platform.

Python FastAPI + Vue 3 (Element Plus) + SQLite 的外贸企业 ERP 系统，覆盖采购、销售、生产、退税、库存等核心业务模块。

- 后端: FastAPI (端口 8788)
- 前端: Vue 3 + Vite (端口 5173)
- 数据库: SQLite (`backend/data/erp.db`)
- 认证: JWT (默认 admin / admin123)

## 模块与路由

### 基础档案 (`/api/foundation`)
- `GET /company` — 公司信息（含联系人）
- `POST /company` — 保存公司信息（仅一条）
- `POST /company/contacts` — 新增联系人
- `PUT /company/contacts/{id}` — 修改联系人
- `DELETE /company/contacts/{id}` — 删除联系人

### 采购管理 (`/api/purchase`)

#### 采购订单 (`/orders`)
- `GET /orders` / `POST /orders` / `PUT /orders/{id}` / `GET /orders/{id}` / `DELETE /orders/{id}`
- 列表返回字段: `received_amount`, `unreceived_amount`, `invoiced_amount`, `uninvoiced_amount`, `paid_amount`, `unpaid_amount`
- 状态流程: 待审核 → 已审核 → 部分入库 → 待开票 → 已开票 → 部分付款 → 已付款
- 状态在列表接口中**动态计算**（覆盖数据库存储的状态），基于实时聚合数据

#### 采购入库 (`/receipts`)
- `POST /receipts` — 入库并更新库存+批次+状态
- `GET /receipts` — 列表
- `DELETE /receipts/{id}` — 取消入库（回滚库存/批次/状态）
- `GET /receipts/{id}` — 详情

#### 采购发票 (`/invoices`)
- `POST /invoices` — 创建发票，自动生成应付账款+进项发票(退税)
- `GET /invoices` / `PUT /invoices/{id}` / `DELETE /invoices/{id}`
- 删除时级联删除进项发票和应付

#### 付款 (`/payments`)
- `POST /payments` — 付款并核销应付
- `GET /payments` / `GET /payments/{id}` / `PUT /payments/{id}` / `DELETE /payments/{id}`
- 删除时回滚应付核销

#### 应付账款 (`/ap`)
- `GET /ap` — 列表

### 销售管理 (`/api/sales`)
- 销售订单 / 发货 / 报关 / 发票 / 应收账款 / 收款

### 退税管理 (`/api/tax-refund`)
- `POST /calculate` — 免抵退计算（可删除）
- `GET /input-invoices` — 进项发票列表
- `POST /declarations` — 创建申报
- `GET /declarations` — 列表（refundable_amount 从明细行实时汇总）
- `GET /declarations/{id}` — 详情（含 rows）
- `DELETE /declarations/{id}` — 删除（回滚发票匹配状态）
- `PUT /declarations/{id}/submit` — 申报（状态变"已申报"）
- `PUT /declarations/{id}/cancel-submit` — 取消申报（回到"待申报"）
- `PUT /declarations/{id}/refund` — 完成退税（输入实际退税金额）
- `PUT /declarations/{id}/cancel-refund` — 取消退税
- `POST /declarations/{id}/rows` — 添加明细行（自动编号+关联号+更新发票匹配状态+更新采购发票状态）
- `PUT /declarations/{id}/rows/{row_id}` — 更新明细行
- `DELETE /declarations/{id}/rows/{row_id}` — 删除明细行（回滚发票状态，重排序号）

### 库存管理 (`/api/inventory`)
- 库存余额 / 库存流水

### 生产管理 (`/api/production`)
- 委外工单 / 完工入库

---

## 关键业务逻辑

### 增值税计算
1. 不含税金额 = 含税金额 / (1 + 税率/100)
2. 税额 = 不含税金额 × 税率/100
3. 含税金额 = 数量 × 单价

### 采购订单状态动态计算
```
待审核 → 已审核 → 部分入库 → 待开票 → 已开票 → 部分付款 → 已付款
```
动态覆盖规则（在列表接口中实时计算，不依赖数据库状态字段）:
- 部分入库: 部分收料且未全部收料
- 待开票: 全部收料但未开票
- 已开票: 已开票但未付款
- 部分付款: 部分付款
- 已付款: 全额付款

### 退税申报流程
```
待申报 → (申报) → 已申报 → (已退税, 输入金额) → 已退税
  ↑                        ↑                          ↓
  └── (取消申报) ────────┘     (取消退税) ←─────────────┘
```
- 待申报: 可修改/删除/申报
- 已申报: 可取消申报/已退税/查看详情
- 已退税: 可取消退税/查看详情
- 实际退税金额在"已退税"时录入，列表中显示

### 采购发票同步
- 创建采购发票时自动：
  1. 生成应付账款（含税金额 = amount + tax_amount）
  2. 生成进项发票（`tr_input_invoice`，状态"未匹配"）
- 发票添加进申报详情时：
  1. 进项发票状态 → "已匹配"
  2. 采购发票状态 → "已匹配(退税)"
- 删除申报/明细行时：
  1. 进项发票状态 → "未匹配"
  2. 采购发票状态 → "未匹配"

### 入库操作
- 从采购订单"入库"按钮 → 路由参数 `?oid=orderId` → 自动弹窗填充明细
- 手工"新建入库" → 选订单 → 自动加载明细
- 两套独立代码路径，不共享逻辑

### 应付/应收账款
- 汇总页签: 按供应商/客户分组，显示笔数/总金额/已付收/余额，可点击切换明细
- 明细页签: 按每笔列，底部合计行
- 模糊搜索实时过滤

---

## 已知问题 / 待办

### 采购入库
- 自动填充弹窗已修复（`batch_no` 变量名错误导致 ReferenceError）

### 销售订单
- 自动计算改为 `@input` 实时触发 + `watch` 深度监听

### 税额计算
- 标准顺序: 不含税 = 含税/(1+税率) → 税额 = 不含税×税率

### 全局 CSS
- `.el-table { table-layout: auto }`
- `.el-table .cell { white-space: nowrap }`

---

## 开发规范

### 字段命名
- 后端传输: snake_case
- 前端 `request.js` 拦截器: 不做响应键转换
- Pydantic schema `from_attributes = True`

### 前端金额/数量格式化
- `$fm(value)` — 金额 `¥1,234,567.89`
- `$fq(value)` — 数量 `1,234.5678`

### 数据库重置
```
kill 后端进程 → rm data/* → 重启后端 → 运行 init_all.py
```

### 测试流程
1. 重置DB
2. 验证后端API
3. 验证前端页面可用
