"""
AI Agent — Function Calling 方案
=================================
LLM 通过工具函数操作 ERP，不再需要解析 JSON 或关键词规则。
"""

import json
import httpx
from datetime import date
from sqlalchemy.orm import Session

from app.models.system_config import BotConfig
from app.utils.crypto import decrypt


# ==================== 工具定义 ====================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_entities",
            "description": "查询档案信息：客户、供应商、物料、产品。支持模糊搜索。",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "enum": ["customer", "supplier", "material", "product"],
                        "description": "要查询的档案类型",
                    },
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词，留空则列出全部",
                    },
                },
                "required": ["entity_type"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_order",
            "description": "创建业务单据。必须先确认所有字段后再调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_type": {
                        "type": "string",
                        "enum": ["purchase_order", "sales_order", "production_order"],
                        "description": "单据类型",
                    },
                    "supplier_name": {"type": "string", "description": "供应商名称（采购单必填）"},
                    "customer_name": {"type": "string", "description": "客户名称（销售单必填）"},
                    "product_name": {"type": "string", "description": "产品名称（销售单/生产单必填）"},
                    "material_name": {"type": "string", "description": "物料名称（采购单必填）"},
                    "quantity": {"type": "number", "description": "数量"},
                    "unit_price": {"type": "number", "description": "单价"},
                    "order_date": {"type": "string", "description": "日期，默认为今天"},
                    "due_date": {"type": "string", "description": "计划完成日（生产单）"},
                },
            },
        }
    },
]

SYSTEM_PROMPT = """你是 MTS 系统的 ERP 助手，通过对话帮助用户完成工作。

## 核心能力
你有两个工具可以在 ERP 系统中执行操作：
1. query_entities — 查询客户/供应商/物料/产品档案
2. create_order — 创建采购/销售/生产订单

## 工作流程

### 查询档案
- 用户说「查xxx/找xxx/xxx编码」→ 直接调 query_entities
- 用户说「全部客户/所有供应商/材料清单」→ keyword 留空
- 查完后把结果用自然的短列表呈现给用户
- **不要编造数据**，一切以 query_entities 返回为准

### 创建订单
创建订单前必须经过「三步确认」：

第一步 — 确认单据类型
  用户说「下单/采购/销售/生产」→ 问清是哪种单
第二步 — 收集字段（如果有缺的）
  purchase：supplier_name, material_name, quantity, unit_price
  sales：customer_name, product_name, quantity, unit_price
  production：product_name, quantity, due_date
第三步 — 逐项确认
  列出全部字段让用户核对，用户说「对/是/确认」再调 create_order

### 对话风格
- 中文，自然，简短，像同事聊天
- 一次只问一件事
- 用户否定就换，不要固执
- 查询结果直接给，不用问要不要
- 不确定用户意图时先反问，不要瞎猜"""


# ==================== 工具执行 ====================

ENTITY_LABELS = {
    "supplier": "供应商", "customer": "客户",
    "material": "物料", "product": "产品",
}


def _execute_query_entities(args: dict, db: Session) -> str:
    """执行 query_entities 工具"""
    from app.models.foundation import Supplier, Customer, Material, Product

    etype = args.get("entity_type")
    keyword = (args.get("keyword") or "").strip()

    MODEL_MAP = {
        "supplier": (Supplier, Supplier.name, "name", ["name", "code", "contact_person", "phone"]),
        "customer": (Customer, Customer.name_cn, "name_cn", ["name_cn", "code", "contact_person", "phone"]),
        "material": (Material, Material.name, "name", ["name", "code", "unit", "spec"]),
        "product": (Product, Product.name_cn, "name_cn", ["name_cn", "code", "spec"]),
    }
    if etype not in MODEL_MAP:
        return f"不支持的查询类型：{etype}"

    model_cls, name_col, name_attr, fields = MODEL_MAP[etype]
    q = db.query(model_cls).filter(model_cls.is_active == 1)
    if keyword:
        q = q.filter(name_col.like(f"%{keyword}%"))
    items = q.limit(100).all()

    if not items:
        label = ENTITY_LABELS.get(etype, etype)
        if keyword:
            return f"未找到匹配的{label}「{keyword}」"
        return f"系统中暂无{label}数据"

    label = ENTITY_LABELS.get(etype, etype)
    lines = [f"📋 找到 {len(items)} 个{label}："]
    for item in items:
        parts = []
        for f in fields:
            v = getattr(item, f, "") or ""
            if f == "name_cn":
                v = f"**{v}**"
            elif f == "code":
                v = f"`{v}`"
            parts.append(str(v))
        lines.append("  " + "｜".join(parts))
    return "\n".join(lines)


def _execute_create_order(args: dict, db: Session) -> str:
    """执行 create_order 工具"""
    from app.models.foundation import Supplier, Customer, Material, Product

    otype = args.get("order_type")
    today = date.today().isoformat()

    try:
        if otype == "purchase_order":
            from app.models.purchase import PurchaseOrder, PurchaseOrderItem
            from app.utils.batch_no import generate_doc_no

            sup_name = args.get("supplier_name", "")
            mat_name = args.get("material_name", "")
            qty = float(args.get("quantity", 0))
            price = float(args.get("unit_price", 0))
            order_date = args.get("order_date", today)

            sup = db.query(Supplier).filter(Supplier.name.like(f"%{sup_name}%"), Supplier.is_active == 1).first()
            if not sup:
                return f"未找到供应商「{sup_name}」，请核实名称"
            mat = db.query(Material).filter(Material.name.like(f"%{mat_name}%"), Material.is_active == 1).first()
            if not mat:
                return f"未找到物料「{mat_name}」，请核实名称"

            order_no = generate_doc_no(db, "PO")
            po = PurchaseOrder(order_no=order_no, supplier_id=sup.id, order_date=_parse_date(order_date),
                               status="待审批", total_amount=round(qty * price, 2), tax_rate=13,
                               remark="通过AI助手创建", created_by="AI")
            db.add(po); db.flush()
            item = PurchaseOrderItem(order_id=po.id, material_id=mat.id, quantity=qty,
                                     unit_price=price, total_amount=round(qty * price, 2), tax_rate=13)
            db.add(item); db.commit()
            return f"✅ **采购订单 {order_no} 已创建！**\n状态：待审批\n可在采购管理查看"

        elif otype == "sales_order":
            from app.models.sales import SalesOrder, SalesOrderItem
            from app.utils.batch_no import generate_doc_no

            cust_name = args.get("customer_name", "")
            prod_name = args.get("product_name", "")
            qty = float(args.get("quantity", 0))
            price = float(args.get("unit_price", 0))
            order_date = args.get("order_date", today)

            cust = db.query(Customer).filter(Customer.name_cn.like(f"%{cust_name}%"), Customer.is_active == 1).first()
            if not cust:
                # 试试英文名
                cust = db.query(Customer).filter(Customer.name_en.like(f"%{cust_name}%"), Customer.is_active == 1).first()
            if not cust:
                return f"未找到客户「{cust_name}」，请核实名称"
            prod = db.query(Product).filter(Product.name_cn.like(f"%{prod_name}%"), Product.is_active == 1).first()
            if not prod:
                return f"未找到产品「{prod_name}」，请核实名称"

            order_no = generate_doc_no(db, "SO")
            so = SalesOrder(order_no=order_no, customer_id=cust.id, order_date=_parse_date(order_date),
                            status="待审核", total_amount=round(qty * price, 2),
                            currency_id=1, exchange_rate=1, remark="通过AI助手创建", created_by="AI")
            db.add(so); db.flush()
            item = SalesOrderItem(order_id=so.id, product_id=prod.id, quantity=qty,
                                  unit_price=price, total_amount=round(qty * price, 2), tax_rate=13)
            db.add(item); db.commit()
            return f"✅ **销售订单 {order_no} 已创建！**\n状态：待审核\n可在销售管理查看"

        elif otype == "production_order":
            from app.models.production import ProductionOrder
            from app.utils.batch_no import generate_doc_no

            prod_name = args.get("product_name", "")
            qty = float(args.get("quantity", 0))
            due = args.get("due_date", "")

            prod = db.query(Product).filter(Product.name_cn.like(f"%{prod_name}%"), Product.is_active == 1).first()
            if not prod:
                return f"未找到产品「{prod_name}」，请核实名称"

            order_no = generate_doc_no(db, "MO")
            mo = ProductionOrder(order_no=order_no, product_id=prod.id, quantity=qty,
                                 due_date=_parse_date(due) if due else None,
                                 status="待排产", remark="通过AI助手创建", created_by="AI")
            db.add(mo); db.commit()
            return f"✅ **生产订单 {order_no} 已创建！**\n状态：待排产\n可在生产管理查看"

        else:
            return f"不支持的单据类型：{otype}"

    except Exception as e:
        db.rollback()
        return f"❌ 创建失败：{e}"


def _parse_date(val):
    if val is None or isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val)[:10])
    except (ValueError, TypeError):
        return date.today()


TOOL_EXECUTORS = {
    "query_entities": _execute_query_entities,
    "create_order": _execute_create_order,
}


# ==================== AI 调用 ====================

def _call_llm(messages: list[dict], bot_config: BotConfig, tool_choice=None) -> dict | None:
    """调用 LLM，支持 function calling"""
    headers = {
        "Authorization": f"Bearer {bot_config.api_key}",
        "Content-Type": "application/json",
    }
    base_url = (bot_config.base_url or "").rstrip("/") or (
        "https://api.deepseek.com" if bot_config.provider == "deepseek"
        else "https://api.openai.com"
    )
    payload = {
        "model": bot_config.model or "deepseek-chat",
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        "temperature": bot_config.temperature or 0.1,
        "max_tokens": bot_config.max_tokens or 2048,
        "tools": TOOLS,
    }
    if tool_choice:
        payload["tool_choice"] = tool_choice

    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(f"{base_url}/v1/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        import logging
        logging.getLogger("ai_chat").error(f"LLM call failed: {e}")
        return None


# ==================== 主流程 ====================

def process_message(message: str, history: list[dict], db: Session) -> dict:
    """
    处理用户消息（核心入口）
    返回 {"reply": str, "state": str, "history": list}
    """
    config = _get_config(db)
    if not config:
        return {"reply": "AI 未配置，请先在系统管理中配置 AI 模型", "state": "error", "history": history or []}

    messages = list(history or [])
    messages.append({"role": "user", "content": message})

    # 最多 3 轮 tool call 循环
    for _ in range(3):
        result = _call_llm(messages, config)
        if not result:
            return {"reply": "AI 调用失败", "state": "error", "history": history or []}

        choice = result["choices"][0]
        msg = choice["message"]

        # LLM 返回文本 → 结束
        if msg.get("content"):
            messages.append({"role": "assistant", "content": msg["content"]})
            # 截断历史（保留最近 20 条）
            if len(messages) > 20:
                messages = messages[-20:]
            return {"reply": msg["content"], "state": "idle", "history": messages}

        # LLM 调用了工具
        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                fn = tc["function"]
                name = fn["name"]
                try:
                    args = json.loads(fn["arguments"])
                except json.JSONDecodeError:
                    args = {}

                # 记录 tool call
                messages.append({
                    "role": "assistant",
                    "tool_calls": [{"id": tc["id"], "type": "function",
                                    "function": {"name": name, "arguments": fn["arguments"]}}],
                })

                # 执行工具
                executor = TOOL_EXECUTORS.get(name)
                if executor:
                    tool_result = executor(args, db)
                else:
                    tool_result = f"未知工具：{name}"

                # 记录工具结果
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_result,
                })
            # 继续循环，让 LLM 处理工具结果
            continue

        break  # 安全兜底

    return {"reply": "抱歉，我暂时无法处理这个请求", "state": "error", "history": history or []}


def _get_config(db: Session) -> BotConfig | None:
    """获取启用的 AI 配置"""
    config = db.query(BotConfig).filter(BotConfig.is_active == 1).first()
    if config and config.api_key:
        config.api_key = decrypt(config.api_key)
    return config
