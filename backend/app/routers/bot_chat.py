"""
MTS Bot 对话引擎 — 会话状态机 + 关键词匹配
=============================================
暂不依赖 AI API，先用关键词规则走通全流程。
配置 AI 模型后自动升级为智能对话。
"""

import json
import re
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func

from app.database import get_db
from app.models.auth import User
from app.models.foundation import Supplier, Customer, Material, Product
from app.utils.auth import get_current_user

router = APIRouter(prefix="/chat", tags=["AI Bot"])


# ==================== 会话管理 ====================

class SessionStore:
    """内存会话存储（后续可改为 Redis/DB）"""
    def __init__(self):
        self._sessions: dict[str, dict] = {}

    def get(self, sid: str) -> dict:
        return self._sessions.get(sid, {"state": "idle", "intent": None, "data": {}})

    def set(self, sid: str, state: dict):
        self._sessions[sid] = state

    def clear(self, sid: str):
        self._sessions.pop(sid, None)


sessions = SessionStore()


# ==================== 关键词规则引擎 ====================

INTENT_KEYWORDS = {
    "purchase_order": ["采购", "下单", "进货", "买", "订购", "po"],
    "sales_order": ["销售", "出货", "卖", "订单", "so", "客户要"],
    "production_order": ["生产", "工单", "做", "制造", "mo", "排产"],
}

QUERY_WORDS = {"查", "查询", "找", "搜索", "看一下"}
QUERY_ENTITIES = {
    "supplier": ["供应商", "厂家"],
    "customer": ["客户", "买家"],
    "material": ["物料", "材料", "原料"],
    "product": ["产品", "商品"],
    "logistics": ["物流", "快递", "货代", "运输"],
}

CONFIRM_WORDS = {"确认", "y", "yes", "对", "是的", "没错", "提交", "可以", "是"}
CANCEL_WORDS = {"取消", "算了", "不要了", "撤销", "取消订单"}
MODIFY_PREFIXES = ["改", "修改", "换", "换成", "变更"]


def detect_query(text: str) -> tuple[str, str] | None:
    """检测是否为查询类请求，返回 (entity_type, search_term)"""
    t = text.strip()
    # 检查是否包含查询关键词
    has_query = any(qw in t for qw in QUERY_WORDS)
    # 检查是否包含"编码"或"号码" — 也是隐式查询
    has_code_query = "编码" in t or "代码" in t or "号码" in t

    if not has_query and not has_code_query:
        return None

    # 识别要查什么实体
    entity_type = None
    for etype, keywords in QUERY_ENTITIES.items():
        for kw in keywords:
            idx = t.find(kw)
            if idx >= 0:
                entity_type = etype
                break
        if entity_type:
            break

    # 提取搜索关键词：去掉查询词和实体词
    search_term = t
    for qw in QUERY_WORDS:
        search_term = search_term.replace(qw, "")
    for kws in QUERY_ENTITIES.values():
        for kw in kws:
            search_term = search_term.replace(kw, "")
    for w in ["的", "编码", "代码", "号码", "叫", "是", "什么", "一下", "信息", "详细"]:
        search_term = search_term.replace(w, "")
    search_term = search_term.strip()

    return entity_type, search_term


def handle_query(entity_type: str, search_term: str, db: Session) -> str:
    """执行查询并返回格式化结果"""
    from app.models.foundation import Supplier, Customer, Material, Product

    if not search_term:
        entity_label = {"supplier": "供应商", "customer": "客户", "material": "物料", "product": "产品", "logistics": "物流"}.get(entity_type, entity_type)
        return f"你想查哪个{entity_label}？说具体名称或关键词"

    like = f"%{search_term}%"

    ENTITY_LABELS = {"supplier": "供应商", "customer": "客户", "material": "物料", "product": "产品", "logistics": "物流"}

    if entity_type == "supplier":
        items = db.query(Supplier).filter(
            Supplier.name.like(like) | Supplier.code.like(like),
            Supplier.is_active == 1
        ).limit(5).all()
        if not items:
            return f"未找到匹配的供应商「{search_term}」"
        lines = [f"📋 找到 {len(items)} 个供应商："]
        for s in items:
            lines.append(f"  **{s.name}**｜编码 `{s.code}`｜{s.contact_person} {s.phone}")
        return "\n".join(lines)

    elif entity_type == "customer":
        items = db.query(Customer).filter(
            (Customer.name_cn.like(like)) | (Customer.code.like(like)),
            Customer.is_active == 1
        ).limit(5).all()
        if not items:
            return f"未找到匹配的客户「{search_term}」"
        lines = [f"📋 找到 {len(items)} 个客户："]
        for c in items:
            lines.append(f"  **{c.name_cn}**｜编码 `{c.code}`｜{c.contact_person} {c.phone}")
        return "\n".join(lines)

    elif entity_type == "material":
        items = db.query(Material).filter(
            Material.name.like(like) | Material.code.like(like),
            Material.is_active == 1
        ).limit(5).all()
        if not items:
            return f"未找到匹配的物料「{search_term}」"
        lines = [f"📋 找到 {len(items)} 个物料："]
        for m in items:
            spec = f" 规格{m.spec}" if m.spec else ""
            lines.append(f"  **{m.name}**｜编码 `{m.code}`｜{m.unit}{spec}")
        return "\n".join(lines)

    elif entity_type == "product":
        items = db.query(Product).filter(
            Product.name_cn.like(like) | Product.code.like(like),
            Product.is_active == 1
        ).limit(5).all()
        if not items:
            return f"未找到匹配的产品「{search_term}」"
        lines = [f"📋 找到 {len(items)} 个产品："]
        for p in items:
            lines.append(f"  **{p.name_cn}**｜编码 `{p.code}`｜规格 {p.spec or '-'}")
        return "\n".join(lines)

    elif entity_type == "logistics":
        # 物流信息 — 先给提示
        return "物流信息查询功能开发中，请联系管理员 🔧"

    return f"暂时不支持查询{ENTITY_LABELS.get(entity_type, entity_type)}"


def detect_intent(text: str) -> str | None:
    """关键词检测意图"""
    t = text.lower()
    for intent, keywords in INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in t:
                return intent
    return None


def extract_field(text: str, field: str, db: Session) -> str | dict | None:
    """从用户文本中提取指定字段"""
    text_lower = text.lower()

    # 数量
    if field == "quantity":
        nums = re.findall(r"\d+\.?\d*", text)
        return float(nums[0]) if nums else None

    # 单价
    if field == "unit_price":
        nums = re.findall(r"\d+\.?\d*", text)
        if len(nums) >= 2:
            return float(nums[1])
        elif len(nums) == 1:
            return float(nums[0])
        return None

    # 日期
    if field == "date":
        today = date.today().isoformat()
        if "今天" in text_lower or "now" in text_lower:
            return today
        m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text)
        if m:
            return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
        return today

    if field == "due_date":
        return extract_field(text, "date", db)

    # 供应商匹配
    if field == "supplier":
        # 提取可能的名称（去掉已知命令词）
        clean = re.sub(r"采购|下单|进货|从|找|给|买", "", text).strip()
        candidates = (
            db.query(Supplier)
            .filter(
                Supplier.name.like(f"%{clean}%"),
                Supplier.is_active == 1,
            )
            .limit(3)
            .all()
        )
        if len(candidates) == 1:
            return {"id": candidates[0].id, "name": candidates[0].name}
        if candidates:
            return {
                "_candidates": [
                    {"id": c.id, "name": c.name} for c in candidates
                ]
            }
        return None

    # 客户匹配
    if field == "customer":
        clean = re.sub(r"销售|出货|卖|给|找", "", text).strip()
        candidates = (
            db.query(Customer)
            .filter(
                Customer.name_cn.like(f"%{clean}%"),
                Customer.is_active == 1,
            )
            .limit(3)
            .all()
        )
        if len(candidates) == 1:
            return {"id": candidates[0].id, "name": candidates[0].name}
        if candidates:
            return {"_candidates": [{"id": c.id, "name": c.name} for c in candidates]}
        return None

    # 物料/产品匹配
    if field in ("material", "product"):
        if field == "material":
            candidates = (
                db.query(Material)
                .filter(Material.name.like(f"%{text}%"), Material.is_active == 1)
                .limit(5)
                .all()
            )
        else:
            candidates = (
                db.query(Product)
                .filter(Product.name_cn.like(f"%{text}%"), Product.is_active == 1)
                .limit(5)
                .all()
            )
        if len(candidates) == 1:
            item = candidates[0]
            if field == "material":
                return {"id": item.id, "name": item.name, "unit": item.unit}
            return {"id": item.id, "name": item.name_cn, "unit": item.unit}
        if candidates:
            items = []
            for c in candidates:
                name = c.name if field == "material" else c.name_cn
                items.append({"id": c.id, "name": name})
            return {"_candidates": items}
        return None

    return None


def parse_confirm(text: str) -> bool | None:
    """检测确认/取消/修改意图"""
    t = text.strip().lower()
    if t in CONFIRM_WORDS:
        return True
    if t in CANCEL_WORDS:
        return False
    return None


# ==================== 字段定义 ====================

INTENT_FIELDS = {
    "purchase_order": [
        ("supplier", "供应商是哪个？"),
        ("material", "采购什么物料？"),
        ("quantity", "数量多少？"),
        ("unit_price", "单价多少？"),
        ("date", "日期是哪天？（默认为今天）"),
    ],
    "sales_order": [
        ("customer", "客户是哪个？"),
        ("product", "销售什么产品？"),
        ("quantity", "数量多少？"),
        ("unit_price", "单价多少？"),
        ("date", "日期是哪天？（默认为今天）"),
    ],
    "production_order": [
        ("product", "生产什么产品？"),
        ("quantity", "数量多少？"),
        ("due_date", "计划完成日是哪天？"),
    ],
}


# ==================== 对话处理 ====================

def process_message(text: str, session: dict, db: Session) -> dict:
    """处理用户消息，返回 Bot 回复"""
    state = session.get("state", "idle")
    intent = session.get("intent")
    data = session.get("data", {})

    # 检查确认/取消
    confirm = parse_confirm(text)
    if confirm is True and state == "confirm":
        return execute_confirm(session, db)
    if confirm is False:
        sessions.clear(session.get("_sid", ""))
        return {"reply": "已取消，需要帮忙随时找我 😊", "state": "cancelled"}

    # 修改字段
    for prefix in MODIFY_PREFIXES:
        if text.startswith(prefix):
            field_name = text[len(prefix):].strip()
            if field_name and field_name in data:
                data.pop(field_name)
                session["state"] = "collecting"
                session["data"] = data
                return {
                    "reply": f"好的，重新告诉我 {field_name}：",
                    "state": "collecting",
                }

    if state == "idle":
        # 检测查询意图（优先于创建单据）
        q = detect_query(text)
        if q and q[0]:
            reply = handle_query(q[0], q[1], db)
            return {"reply": reply, "state": "idle"}

        # 检测创建单据意图
        detected = detect_intent(text)
        if not detected:
            return {
                "reply": (
                    "你好！我可以帮你：\n\n"
                    "📋 **创建单据**\n"
                    "  「采购PCB板100片」— 创建采购订单\n"
                    "  「销售产品A」— 创建销售订单\n"
                    "  「生产工单」— 创建生产订单\n\n"
                    "🔍 **查询档案**\n"
                    "  「查一下客户深圳电子」— 查客户信息\n"
                    "  「找供应商编码」— 查供应商\n"
                    "  「查物料名称」— 查物料\n\n"
                    "你想做什么？"
                ),
                "state": "idle",
            }
        session["intent"] = detected
        session["state"] = "collecting"
        session["data"] = {}
        # 立即尝试从第一句话提取字段
        return collect_fields(text, session, db)

    if state == "collecting":
        # 只提取当前第一个缺失字段
        fields = INTENT_FIELDS.get(intent, [])
        for field_key, question in fields:
            if field_key not in data:
                val = extract_field(text, field_key, db)
                if val is not None:
                    if isinstance(val, dict) and "_candidates" in val:
                        candidates = val["_candidates"]
                        reply_lines = [f"找到多个，请选择："]
                        for i, c in enumerate(candidates, 1):
                            reply_lines.append(f"  {i}. {c['name']}")
                        reply_lines.append("回复编号或全称")
                        return {"reply": "\n".join(reply_lines), "state": "collecting"}
                    data[field_key] = val
                    # 成功提取一个字段后重新检查是否全部齐了
                    return collect_fields(text, session, db)
                # 没提取到 — 再问一次这个字段
                return {"reply": question, "state": "collecting"}

        # 所有字段齐了
        session["state"] = "confirm"
        return show_confirm(session, db)

    return {"reply": "我没理解，能再说一遍吗？", "state": state}


def collect_fields(text: str, session: dict, db: Session) -> dict:
    """逐步收集字段"""
    intent = session["intent"]
    data = session["data"]
    fields = INTENT_FIELDS.get(intent, [])

    for field_key, question in fields:
        if field_key not in data:
            return {
                "reply": question,
                "state": "collecting",
            }

    # 所有字段齐了 — 进入确认
    session["state"] = "confirm"
    return show_confirm(session, db)


def show_confirm(session: dict, db: Session) -> dict:
    """展示确认信息"""
    intent = session["intent"]
    data = session["data"]
    intent_names = {
        "purchase_order": "采购订单",
        "sales_order": "销售订单",
        "production_order": "生产订单",
    }

    lines = [f"📋 **{intent_names.get(intent, intent)} 确认：**"]

    if intent == "purchase_order":
        sup = data.get("supplier", {})
        if isinstance(sup, dict):
            lines.append(f"  供应商：{sup.get('name', '?')}")
        mat = data.get("material", {})
        if isinstance(mat, dict):
            lines.append(f"  物料：{mat.get('name', '?')} × {data.get('quantity', '?')}")
        lines.append(f"  单价：¥{data.get('unit_price', '?')}")
        lines.append(f"  日期：{data.get('date', date.today().isoformat())}")
        amt = float(data.get("quantity", 0)) * float(data.get("unit_price", 0))
        lines.append(f"  合计金额：¥{amt:.2f}")

    elif intent == "sales_order":
        cust = data.get("customer", {})
        if isinstance(cust, dict):
            lines.append(f"  客户：{cust.get('name', '?')}")
        prod = data.get("product", {})
        if isinstance(prod, dict):
            lines.append(f"  产品：{prod.get('name', '?')} × {data.get('quantity', '?')}")
        lines.append(f"  单价：¥{data.get('unit_price', '?')}")
        lines.append(f"  日期：{data.get('date', date.today().isoformat())}")

    elif intent == "production_order":
        prod = data.get("product", {})
        if isinstance(prod, dict):
            lines.append(f"  产品：{prod.get('name', '?')} × {data.get('quantity', '?')}")
        lines.append(f"  计划完成：{data.get('due_date', '?')}")

    lines.append("")
    lines.append("回复 **确认** 提交，或 **取消** 放弃，或 **改字段名** 修改（如「改数量」）")

    return {"reply": "\n".join(lines), "state": "confirm"}


def execute_confirm(session: dict, db: Session) -> dict:
    """确认后创建单据"""
    intent = session["intent"]
    data = session["data"]
    sid = session.get("_sid", "")
    sessions.clear(sid)

    try:
        if intent == "purchase_order":
            return create_purchase_from_bot(data, db)
        elif intent == "sales_order":
            return create_sales_from_bot(data, db)
        elif intent == "production_order":
            return create_production_from_bot(data, db)
    except Exception as e:
        return {"reply": f"❌ 创建失败：{str(e)}", "state": "error"}

    return {"reply": "✅ 单据已创建！", "state": "done"}


def create_purchase_from_bot(data: dict, db: Session) -> dict:
    """Bot 创建采购订单"""
    from app.models.purchase import PurchaseOrder, PurchaseOrderItem
    from app.models.inventory import StockTransaction
    from app.utils.batch_no import generate_doc_no

    supplier = data.get("supplier", {})
    material = data.get("material", {})
    qty = float(data.get("quantity", 0))
    price = float(data.get("unit_price", 0))
    order_date = data.get("date", date.today().isoformat())
    sid = supplier.get("id") if isinstance(supplier, dict) else None
    mid = material.get("id") if isinstance(material, dict) else None

    order_no = generate_doc_no(db, "PO")
    po = PurchaseOrder(
        order_no=order_no,
        supplier_id=sid,
        order_date=_parse_date(order_date),
        status="待审批",
        total_amount=round(qty * price, 2),
        tax_rate=13,
        created_by="Bot",
        remark="通过AI Bot创建",
    )
    db.add(po)
    db.flush()

    item = PurchaseOrderItem(
        order_id=po.id,
        material_id=mid,
        quantity=qty,
        unit_price=price,
        total_amount=round(qty * price, 2),
        tax_rate=13,
    )
    db.add(item)
    db.commit()

    return {
        "reply": f"✅ **采购订单 {order_no} 已创建！**\n  状态：待审批\n  可在采购管理查看",
        "state": "done",
    }


def create_sales_from_bot(data: dict, db: Session) -> dict:
    """Bot 创建销售订单"""
    from app.models.sales import SalesOrder, SalesOrderItem
    from app.utils.batch_no import generate_doc_no

    customer = data.get("customer", {})
    product = data.get("product", {})
    qty = float(data.get("quantity", 0))
    price = float(data.get("unit_price", 0))
    order_date = data.get("date", date.today().isoformat())
    cid = customer.get("id") if isinstance(customer, dict) else None
    pid = product.get("id") if isinstance(product, dict) else None

    order_no = generate_doc_no(db, "SO")
    so = SalesOrder(
        order_no=order_no,
        customer_id=cid,
        order_date=_parse_date(order_date),
        status="待审核",
        total_amount=round(qty * price, 2),
        currency_id=1,
        exchange_rate=1,
        remark="通过AI Bot创建",
        created_by="Bot",
    )
    db.add(so)
    db.flush()

    item = SalesOrderItem(
        order_id=so.id,
        product_id=pid,
        quantity=qty,
        unit_price=price,
        total_amount=round(qty * price, 2),
        tax_rate=13,
    )
    db.add(item)
    db.commit()

    return {
        "reply": f"✅ **销售订单 {order_no} 已创建！**\n  状态：待审核\n  可在销售管理查看",
        "state": "done",
    }


def create_production_from_bot(data: dict, db: Session) -> dict:
    """Bot 创建生产订单"""
    from app.models.production import ProductionOrder
    from app.utils.batch_no import generate_doc_no

    product = data.get("product", {})
    qty = float(data.get("quantity", 0))
    due = data.get("due_date")
    pid = product.get("id") if isinstance(product, dict) else None

    order_no = generate_doc_no(db, "MO")
    mo = ProductionOrder(
        order_no=order_no,
        product_id=pid,
        quantity=qty,
        due_date=_parse_date(due) if due else None,
        status="待排产",
        remark="通过AI Bot创建",
        created_by="Bot",
    )
    db.add(mo)
    db.commit()

    return {
        "reply": f"✅ **生产订单 {order_no} 已创建！**\n  状态：待排产\n  可在生产管理查看",
        "state": "done",
    }


def _parse_date(val):
    if val is None or isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val)[:10])
    except (ValueError, TypeError):
        return date.today()


# ==================== API 端点 ====================


@router.post("/message")
def chat_message(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """发送消息给 Bot"""
    text = (body.get("message") or "").strip()
    session_id = body.get("session_id")

    if not text:
        raise HTTPException(400, "消息不能为空")

    # 获取或创建会话
    session = sessions.get(session_id) if session_id else {"state": "idle", "intent": None, "data": {}}
    session["_sid"] = session_id or current_user.username

    # 处理
    result = process_message(text, session, db)

    # 保存会话
    if result.get("state") in ("done", "cancelled", "error"):
        sessions.clear(session["_sid"])
    else:
        sessions.set(session["_sid"], session)

    return {
        "reply": result["reply"],
        "state": result.get("state", "idle"),
        "session_id": session["_sid"],
    }


@router.post("/reset")
def chat_reset(body: dict):
    """重置会话"""
    sid = body.get("session_id", "")
    if sid:
        sessions.clear(sid)
    return {"message": "会话已重置"}
