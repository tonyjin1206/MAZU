# v1.2.0 — RBAC 用户权限体系 改动文档

> 发布日期：2026-07-29
> 基于 `sale_order_update` 分支

---

## 一、概述

本次升级在 MTS 中引入完整的 **RBAC（Role-Based Access Control）** 用户权限体系，替代原先简单的 `role` 字符串字段。新增用户管理、角色管理两个系统页面，支持自定义角色和细粒度权限分配。

---

## 二、数据库变更

### 新增表

| 表名 | 说明 | 字段 |
|------|------|------|
| `sys_role` | 角色定义 | id, name, code(唯一), description, is_system, created_at, updated_at |
| `sys_permission` | 权限定义 | code(主键), name, module, description, created_at |
| `sys_role_permission` | 角色-权限关联 | id, role_id(FK), permission_code(FK) |

### 修改表

**`sys_user`**：
- 新增 `role_id` (INTEGER, FK → sys_role.id) — 外键关联角色
- 删除 `role` 字符串字段（已被 `role_id` 替代）

### 种子数据

启动时自动插入 16 个权限码和 4 个预置角色：

```python
# 权限：8 模块 × 2~3 级 = 16 个
dashboard:read          # 工作台
foundation:read/write   # 基础档案
purchase:read/write/approve  # 采购
sales:read/write/approve     # 销售
production:read/write   # 生产
inventory:read/write    # 库存
tax:read/write          # 退税
system:admin            # 系统管理

# 角色：
管理员  → 全部 16 权限
经理    → 15 权限（不含 system:admin）
操作员  → 12 权限（不含 *:approve 和 system:admin）
只读    → 8 权限（仅 *:read + dashboard:read）
```

---

## 三、后端 API

### 新增端点

| 方法 | 路径 | 权限要求 | 说明 |
|------|------|----------|------|
| `GET` | `/api/auth/permissions` | 登录 | 按模块分组的所有权限列表 |
| `GET` | `/api/auth/roles` | 登录 | 角色列表（含权限码和用户数） |
| `POST` | `/api/auth/roles` | 管理员 | 创建自定义角色 |
| `PUT` | `/api/auth/roles/{id}` | 管理员 | 编辑角色（名称、描述、权限） |
| `DELETE` | `/api/auth/roles/{id}` | 管理员 | 删除角色（非内置） |
| `GET` | `/api/auth/users/{id}` | 登录 | 获取单个用户 |
| `PUT` | `/api/auth/users/{id}` | 管理员 | 更新用户（支持改密码/角色） |
| `DELETE` | `/api/auth/users/{id}` | 管理员 | 删除用户 |
| `GET` | `/api/auth/me/permissions` | 登录 | 当前用户有效权限码列表 |

### 权限检查依赖

```python
from app.utils.auth import require_permission

@router.get("/orders", tags=["采购管理"])
def list_orders(
    ...,
    current_user = Depends(require_permission("purchase:read")),
):
```

---

## 四、前端新增页面

### 用户管理页 `/system/users`

- 表格：用户名、显示名、邮箱、角色标签（颜色编码）、状态、创建时间
- 操作：新建、编辑、分配角色（下拉框）、启用/停用、删除（admin 不可删）
- 搜索：按用户名/显示名实时过滤

### 角色管理页 `/system/roles`

- 表格：角色名称、编码、权限标签、用户数、是否内置、描述
- 操作：新建（输入名称+编码+描述+勾选权限）、编辑、删除（内置不可删）
- 权限选择：按模块分组显示，多选 checkbox

---

## 五、前后端交互

### 权限数据流

```
登录 → POST /api/auth/login → 存 token + user
     → GET /api/auth/me/permissions → 存 localStorage.permissions
     ↓
页面渲染 → $hasPermission('purchase:approve') → 控制按钮显隐
API 请求 → Depends(require_permission('purchase:read')) → 后端校验
401 响应 → 清除 localStorage 中的 token/user/permissions → 跳转登录
```

### 全局方法

```javascript
// main.js 注册
app.config.globalProperties.$hasPermission = (code) => {
  const perms = JSON.parse(localStorage.getItem('permissions') || '[]')
  return perms.includes(code)
}
```

---

## 六、改动文件清单

### 后端（7 文件）

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/models/auth.py` | ✅ 重写 | 新增 Role, Permission, RolePermission 模型；User 加 role_id + role 属性 |
| `backend/app/schemas/auth.py` | ✅ 重写 | 新增 RoleCreate/Update/Out, PermissionOut, PermissionGroup, UserOut 增强 |
| `backend/app/utils/auth.py` | ✅ 更新 | 新增 require_permission() 依赖工厂 |
| `backend/app/routers/auth.py` | ✅ 重写 | 新增角色/权限 CRUD 路由，用户 CRUD 增强 |
| `backend/app/models/__init__.py` | ✅ 更新 | 注册 Role, Permission, RolePermission |
| `backend/app/main.py` | ✅ 更新 | 移除重复的 on_event startup，新增 _seed_rbac() 种子逻辑 |

### 前端（7 文件）

| 文件 | 操作 | 说明 |
|------|------|------|
| `frontend/src/api/foundation.js` | ✅ 更新 | 新增 authApi（角色/权限/用户全部端点） |
| `frontend/src/api/request.js` | ✅ 更新 | 401 拦截增加清除 permissions |
| `frontend/src/router/index.js` | ✅ 更新 | 新增 `/system/users` 和 `/system/roles` 路由 |
| `frontend/src/views/system/Users.vue` | 🆕 新建 | 用户管理完整页面 |
| `frontend/src/views/system/Roles.vue` | 🆕 新建 | 角色管理完整页面 |
| `frontend/src/components/Layout.vue` | ✅ 更新 | 新增系统管理菜单 + 标题 + 退出清除权限 |
| `frontend/src/main.js` | ✅ 更新 | 注册 $hasPermission 全局方法 |
| `frontend/src/views/Login.vue` | ✅ 更新 | 登录后自动拉取权限 |

---

## 七、重置数据库

由于 `sys_user` 表 schema 变更，首次启动需重建数据库：

```bash
cd backend
rm -rf data/erp.db
python run.py     # 启动后自动种子数据
```

默认管理员：`admin` / `admin123`，自动关联管理员角色，拥有全部权限。

---

## 八、31 项自动化验证通过

覆盖：健康检查、登录、角色列表、权限分组、用户 CRUD、角色 CRUD、操作员权限隔离、内置角色保护、自定义角色创建/编辑/删除、用户角色分配、密码修改、用户删除。全部通过。
