"""契约测试：前端 API 调用 ⇄ 后端路由自动比对

三层逻辑：
- 解析层：扫描 frontend/src/api/*.js，把嵌套 API 对象（含 crudApi 模板）解析成
  {导出名: {方法链: (method, 路径模板)}}。
- 使用层：扫描 frontend/src/views/*.vue，提取页面实际调用的方法链。
- 断言层：
  层1 = 页面【在用】的 API 定义，后端必须有路由（缺失 = 浏览器必报错 → 失败）；
        定义了但页面未使用的接口缺失 → 报告"待确认"，不计失败（可能是遗留代码）。
  层2 = 页面直接 request.get/post/...('path') 的调用，后端必须有路由（→ 失败）。

已知问题（KNOWN_ISSUES）：委外工单相关接口后端缺失，是否为废弃功能待业务流验证，
故先标记不计失败，但会在报告中显著列出。
"""

import re
from pathlib import Path

# 后端 tests/ 目录 → 仓库根目录 → frontend/src
REPO_ROOT = Path(__file__).resolve().parents[2]
FE_API_DIR = REPO_ROOT / "frontend" / "src" / "api"
FE_VIEWS_DIR = REPO_ROOT / "frontend" / "src" / "views"

# 已知问题：委外功能已清理（2026-07-31），暂无已知问题
# 格式: {(method, path): "说明"} —— 有已知问题时可重新启用
KNOWN_ISSUES = {}


# ---------- 后端路由 ----------

def collect_backend_routes(app):
    """后端所有路由 → {(method, path)}，去掉 /api 前缀，参数名统一为 {p}"""
    routes = set()
    for r in app.routes:
        methods = getattr(r, "methods", None)
        path = getattr(r, "path", None)
        if methods and path:
            for m in methods:
                routes.add((m, normalize_path(re.sub(r"^/api", "", path))))
    return routes


def normalize_path(path: str) -> str:
    """路径模板统一：/users/{user_id} → /users/{p}（忽略参数名差异）"""
    return re.sub(r"\{[^}]+\}", "{p}", path)


def normalize_fe_path(path: str) -> str:
    """前端路径模板 → 后端风格：/orders/${id} → /orders/{p}，去 query/尾斜杠"""
    path = path.split("?")[0]
    path = path.rstrip("/")
    path = re.sub(r"\$\{([^}]+)\}", "{p}", path)
    return normalize_path(path)


# ---------- 前端 API 定义解析 ----------

CRUD_API_TPL = [
    ("GET", "/foundation/{prefix}", "list"),
    ("GET", "/foundation/{prefix}/{{id}}", "get"),
    ("POST", "/foundation/{prefix}", "create"),
    ("PUT", "/foundation/{prefix}/{{id}}", "update"),
    ("DELETE", "/foundation/{prefix}/{{id}}", "delete"),
    ("GET", "/foundation/{prefix}-select", "select"),
]

REQ_CALL = re.compile(
    r"(\w+):\s*(?:\([^)]*\)\s*=>\s*)?request\.(get|post|put|delete|patch)"
    r"\(\s*[`'\"]([^`'\"]+)[`'\"]"
)


def _parse_block(block: str, indent: int, prefix: str, fname: str):
    """按缩进解析对象块 → {chain: (method, raw_path, origin)}"""
    calls = {}
    lines = block.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith(("//", "*")):
            i += 1
            continue
        leading = len(line) - len(line.lstrip(" "))
        if leading != indent:
            i += 1
            continue

        # 子块：parent: { ... }
        m = re.match(r"(\w+):\s*\{", stripped)
        if m:
            parent = m.group(1)
            j = i + 1
            sub_lines = []
            while j < len(lines):
                l2 = lines[j]
                l2_leading = len(l2) - len(l2.lstrip(" "))
                l2_strip = l2.strip()
                if l2_leading <= indent and l2_strip and not l2_strip.startswith(("//", "*")):
                    break
                sub_lines.append(l2)
                j += 1
            calls.update(_parse_block("\n".join(sub_lines), indent + 2, f"{prefix}{parent}.", fname))
            i = j
            continue

        # crudApi('prefix') 模板
        m = re.match(r"(\w+):\s*crudApi\(\s*'([^']+)'\s*\)", stripped)
        if m:
            key, pfx = m.group(1), m.group(2)
            for method, tpl, sub in CRUD_API_TPL:
                calls[f"{prefix}{key}.{sub}"] = (
                    method, tpl.format(prefix=pfx), f"crudApi('{pfx}')")
            i += 1
            continue

        # request 直接调用
        m = REQ_CALL.match(stripped)
        if m:
            calls[f"{prefix}{m.group(1)}"] = (m.group(2).upper(), m.group(3), fname)
        i += 1
    return calls


def collect_frontend_api_defs():
    """解析所有 api 文件 → {export_name: {chain: (method, raw_path, origin)}}"""
    defs = {}
    for f in sorted(FE_API_DIR.glob("*.js")):
        if f.name == "request.js":
            continue
        src = f.read_text(encoding="utf-8")
        for m in re.finditer(r"export const (\w+)\s*=\s*\{", src):
            name = m.group(1)
            start = m.end()
            depth, i = 1, start
            while depth > 0 and i < len(src):
                if src[i] == "{":
                    depth += 1
                elif src[i] == "}":
                    depth -= 1
                i += 1
            block = src[start:i - 1]
            defs[name] = _parse_block(block, 2, "", f.name)
    return defs


# ---------- 前端页面使用扫描 ----------

def collect_view_api_usage():
    """views/*.vue 中实际调用的 API 链 → set[(export_name, chain)]"""
    used = set()
    for f in sorted(FE_VIEWS_DIR.rglob("*.vue")):
        src = f.read_text(encoding="utf-8")
        for m in re.finditer(
            r"(\w+Api)\.([a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*)*)\s*\(", src
        ):
            used.add((m.group(1), m.group(2)))
    return used


def collect_view_direct_calls():
    """views/*.vue 里直接 request.get/post/...('path') 的调用"""
    calls = set()
    for f in sorted(FE_VIEWS_DIR.rglob("*.vue")):
        src = f.read_text(encoding="utf-8")
        rel = f.relative_to(FE_VIEWS_DIR).as_posix()
        for m in re.finditer(
            r"request\.(get|post|put|delete|patch)\(\s*[`'\"]([^`'\"]+)[`'\"]", src
        ):
            calls.add((m.group(1).upper(), normalize_fe_path(m.group(2)), rel))
    return calls


# ---------- 测试 ----------

def test_contract_layer1_used_api_defs_have_backend_routes(app):
    """层1：页面在用的前端 API 定义，后端必须有路由；未使用的缺失仅报告"""
    backend = collect_backend_routes(app)
    defs = collect_frontend_api_defs()
    used = collect_view_api_usage()

    missing_used, missing_unused = [], []

    for export, chains in sorted(defs.items()):
        for chain, (method, raw_path, origin) in sorted(chains.items()):
            if "${" in raw_path:  # 动态模板无法静态比对
                continue
            path = normalize_fe_path(raw_path)
            if (method, path) in backend or (method, path) in KNOWN_ISSUES:
                continue
            full_chain = f"{export}.{chain}"
            is_used = any(
                exp == export and (c == chain or c.startswith(chain + "."))
                for exp, c in used
            )
            item = (method, path, full_chain, origin)
            (missing_used if is_used else missing_unused).append(item)

    print("\n===== 契约报告 · 层1（API 定义 → 后端路由）=====")
    print(f"前端 API 定义 {sum(len(c) for c in defs.values())} 个，页面在用 {len(used)} 处，后端路由 {len(backend)} 个\n")
    if missing_used:
        print("⚠ 页面【在用】但后端缺失（浏览器必报错）：")
        for m, p, chain, origin in missing_used:
            print(f"  [必报错] {m:6s} {p}  <- {chain} ({origin})")
    if missing_unused:
        print("\nℹ 定义了但页面未使用、后端缺失（遗留代码？待确认）：")
        for m, p, chain, origin in missing_unused:
            print(f"  [待确认] {m:6s} {p}  <- {chain} ({origin})")
    for key, note in sorted(KNOWN_ISSUES.items()):
        print(f"  [已知问题] {key[0]:6s} {key[1]}  ({note})")

    assert not missing_used, (
        f"页面在用的 {len(missing_used)} 个接口后端不存在（浏览器必报错）:\n"
        + "\n".join(f"  {m} {p} <- {chain}" for m, p, chain, _ in missing_used)
    )


def _route_matches(literal_path: str, template_path: str) -> bool:
    """字面路径是否命中路由模板：/params/group/material_main_category → /params/group/{p}

    layer2 收集的是页面里的字面路径（无 `${}`），而后端是参数模板；
    逐段比对，模板段 {p} 通配任意一段字面值。
    """
    lp = literal_path.rstrip("/").split("/")
    tp = template_path.rstrip("/").split("/")
    if len(lp) != len(tp):
        return False
    return all(t == "{p}" or t == l for t, l in zip(tp, lp))


def test_contract_layer2_views_direct_calls_have_backend_routes(app):
    """层2：页面直接调用的接口，后端必须存在"""
    backend = collect_backend_routes(app)
    view_calls = collect_view_direct_calls()

    missing = [
        (m, p, src) for (m, p, src) in view_calls
        if (m, p) not in backend
        and not any(m == bm and _route_matches(p, bp) for bm, bp in backend)
        and (m, p) not in KNOWN_ISSUES
    ]

    print("\n===== 契约报告 · 层2（页面直接调用）=====")
    print(f"页面直接调用 {len(view_calls)} 个接口")
    for m, p, src in sorted(view_calls):
        hit = (m, p) in backend or any(m == bm and _route_matches(p, bp) for bm, bp in backend)
        if (m, p) in KNOWN_ISSUES:
            print(f"  [已知问题] {m:6s} {p}  <- {src}")
        elif not hit:
            print(f"  [缺失]     {m:6s} {p}  <- {src}")

    assert not missing, (
        f"页面直接调用了 {len(missing)} 个后端不存在的接口（浏览器必报错）:\n"
        + "\n".join(f"  {m} {p} <- {src}" for m, p, src in sorted(missing))
    )
