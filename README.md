# Lightweight Trade Management Platform (LTMP)

> 面向中小外贸企业的轻量化管理平台  
> 采购 · 销售 · 生产 · 库存 · 财务 · 退税 — 全链路数字化

---

## 快速开始

### 1. 安装

打开终端，进入解压后的目录，执行一条命令即可：

```bash
chmod +x install.sh && ./install.sh
```

脚本会自动完成以下操作：

| 步骤 | 说明 |
|------|------|
| ① 检测系统环境 | 检查是否已安装 Python 和 Node.js |
| ② 安装系统依赖 | 通过 Homebrew 自动安装缺失的 Python / Node.js |
| ③ 安装后端依赖 | 创建 Python 虚拟环境，pip 安装 FastAPI 等依赖 |
| ④ 安装前端依赖 | npm 安装 Vue 3、Element Plus 等依赖 |
| ⑤ 构建前端 | 编译生成静态文件 |
| ⑥ 启动服务 | 自动启动后端（8788端口）和前端（5173端口） |

> ⏱ 首次安装约需 3-5 分钟（取决于网络速度）

### 2. 使用

安装完成后浏览器自动可访问：

| 地址 | 说明 |
|------|------|
| `http://localhost:5173` | 前端系统界面 |
| `http://localhost:8788` | 后端 API（可直接请求接口） |

**默认账户：** `admin` / `admin123`

### 3. 停止

在终端按 `Ctrl+C` 即可停止所有服务。

---

## 手动启动

如果不想使用一键脚本，也可以分别启动：

```bash
# 终端 1：启动后端
cd backend
source venv/bin/activate
python3 run.py

# 终端 2：启动前端
cd frontend
npm run dev
```

---

## 系统要求

| 组件 | 最低版本 |
|------|---------|
| 操作系统 | macOS 12+（Intel 或 Apple Silicon） |
| Python | 3.10 或更高 |
| Node.js | 18 或更高 |
| 内存 | 4GB 以上 |
| 磁盘 | 500MB 可用空间 |

---

## 功能模块

```
基础档案 → 客户 / 供应商 / 物料 / 产品 / BOM / 工序 / HS编码
采购管理 → 采购订单 → 采购入库 → 采购发票 → 应付账款 → 付款
销售管理 → 销售订单 → 销售发货 → 销售发票 → 应收账款 → 收款
生产管理 → 生产订单 → 派产 → 发料 → 完工 → 成品入库 / 委外 / 加工费发票
库存管理 → 库存余额 / 库存流水 / 批次追溯
退税申报 → 申报期管理 / 发票关联 / 状态跟踪
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
