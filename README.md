# Mazu Trade System (MTS)

> **v2.1.0** — Mazu Trade System — A Lightweight Trade Management Platform  
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
基础档案 → 客户 / 供应商 / 物料 / 产品 / BOM / 工序 / HS编码
采购管理 → 采购订单 → 采购入库 → 采购发票 → 应付账款 → 付款
销售管理 → 销售订单 → 销售发货 → 销售发票 → 应收账款 → 收款
生产管理 → 生产订单 → 派产 → 发料 → 完工 → 成品入库 / 委外 / 加工费发票
库存管理 → 库存余额 / 库存流水 / 批次追溯
退税申报 → 申报期管理 / 发票关联 / 状态跟踪
AI 助手 → 自然语言对话式操作 / 客户/供应商/物料/产品查询 / 创建单据 / 收款/付款 / 发票录入 / 委外/发料/入库
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
