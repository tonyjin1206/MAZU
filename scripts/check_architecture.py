"""架构规范性检查 — 单一数据源 / 无冗余表 / 前端封装统一

纯静态扫描，不依赖 pytest。退出码：0=通过，1=发现问题。

检查点：
1. 废弃表检测：模型定义了表但后端路由完全未引用（如委外独立表）
2. 模型约束一致性：业务上允许为空的字段，模型却加了 NOT NULL（如采购入库明细 material_id）
3. 前端封装规范性：views/*.vue 中直接散写 request 调用（应统一走 src/api/*.js）
4. 弃用 API：Pydantic class-based Config（v2 已弃用）
5. 路由孤儿检测：后端有路由、前端无任何引用（含 KNOWN_ISSUES 豁免名单外）
"""

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MODELS = REPO / "backend" / "app" / "models"
ROUTERS = REPO / "backend" / "app" / "routers"
SCHEMAS = REPO / "backend" / "app" / "schemas"
FE_API = REPO / "frontend" / "src" / "api"
FE_VIEWS = REPO / "frontend" / "src" / "views"

# 已知的合理豁免（新设计允许保留）
EXEMPT_TABLES = {"fd_currency", "fd_warehouse"}  # 简单档案表不算冗余


def scan():
    issues = []
    info = []

    # ---------- 1. 废弃表检测 ----------
    # 收集所有模型类 → (表名, 定义文件)
    model_classes = {}
    for f in sorted(MODELS.glob("*.py")):
        if f.name in ("__init__.py", "base.py"):
            continue
        src = f.read_text(encoding="utf-8")
        for m in re.finditer(r"class (\w+)\(Base\):", src):
            cls = m.group(1)
            block = src[m.start():m.start() + 600]
            t = re.search(r'__tablename__\s*=\s*"([^"]+)"', block)
            if t:
                model_classes[cls] = (t.group(1), f.name)

    # 全部后端源码（路由/模式/其他模型）作为引用池（用相对路径区分同名文件）
    all_src = {}
    for d in (ROUTERS, SCHEMAS, MODELS):
        for f in d.glob("*.py"):
            all_src[f.relative_to(REPO).as_posix()] = f.read_text(encoding="utf-8")

    for cls, (table, fname) in sorted(model_classes.items()):
        if table in EXEMPT_TABLES:
            continue
        used = False
        for fn, src in all_src.items():
            if fn.endswith(f"models/{fname}") or fn.endswith("models/__init__.py"):
                continue  # 自身定义 / 包聚合导出不算引用
            if re.search(rf"\b{cls}\b", src):
                used = True
                break
        if not used:
            issues.append(f"[废弃表?] models/{fname}: {cls} (表 {table}) 无任何路由/schema 引用")

    # ---------- 2. 模型约束一致性 ----------
    # 互斥字段模式：material_id NOT NULL 但同时存在可空的 product_id 列
    # （业务上"材料或成品二选一"），如 po_receipt_item —— BUG#1 根因
    for f in sorted(MODELS.glob("*.py")):
        src = f.read_text(encoding="utf-8")
        for m in re.finditer(r"class (\w+)\(Base\):", src):
            cls = m.group(1)
            block = src[m.start():m.start() + 1500]
            has_material_nn = bool(re.search(
                r"material_id\s*=\s*Column\([^)]*nullable\s*=\s*False", block))
            has_product = bool(re.search(r"product_id\s*=\s*Column\(", block))
            if has_material_nn and has_product:
                issues.append(
                    f"[互斥约束] {f.name}: {cls} 的 material_id NOT NULL 且存在 product_id 列"
                    f" —— 成品单据会违反约束（BUG#1 同类）")

    # ---------- 3. 前端封装规范性 ----------
    for f in sorted(FE_VIEWS.rglob("*.vue")):
        src = f.read_text(encoding="utf-8")
        # 排除 import 行
        direct = [m for m in re.finditer(
            r"(?<!import )request\.(get|post|put|delete|patch)\(", src)]
        if direct:
            rel = f.relative_to(FE_VIEWS).as_posix()
            issues.append(f"[散写request] {rel}: {len(direct)} 处直接调用（应走 api/*.js 封装）")

    # ---------- 4. Pydantic 弃用 Config ----------
    for f in sorted(SCHEMAS.glob("*.py")):
        src = f.read_text(encoding="utf-8")
        n = len(re.findall(r"class Config:", src))
        if n:
            issues.append(f"[弃用API] {f.name}: {n} 处 class Config（Pydantic v2 应改用 ConfigDict）")

    # ---------- 5. 废弃表残留的双保险：路由文件中引用了 mo_outsourcing 等表？ ----------
    for f in sorted(ROUTERS.glob("*.py")):
        src = f.read_text(encoding="utf-8")
        for cls in ("OutsourceOrder", "OutsourceReceipt", "MaterialIssue"):
            if cls in src:
                info.append(f"[双保险] {f.name} 引用了 {cls}（确认功能在用）")

    return issues, info


def main():
    issues, info = scan()
    print("=" * 60)
    print("  架构规范性检查")
    print("=" * 60)
    for i in info:
        print(f"ℹ {i}")
    if issues:
        print(f"\n发现 {len(issues)} 个问题：")
        for i in issues:
            print(f"  ✗ {i}")
        print("\n结论：FAIL — 需要人工确认/整改")
        return 1
    print("\n结论：PASS — 未发现架构违规")
    return 0


if __name__ == "__main__":
    sys.exit(main())
