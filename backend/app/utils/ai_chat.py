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
            "description": "查询档案信息：客户、供应商、物料、产品、应收/应付账款、发票清单。支持模糊搜索。",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "enum": ["customer", "supplier", "material", "product",
                                 "receivable", "payable", "purchase_invoice", "sales_invoice"],
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
            "description": "创建采购订单或销售订单。必须先确认所有字段后再调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_type": {
                        "type": "string",
                        "enum": ["purchase_order", "sales_order"],
                        "description": "单据类型",
                    },
                    "supplier_name": {"type": "string", "description": "供应商名称（采购单必填）"},
                    "customer_name": {"type": "string", "description": "客户名称（销售单必填）"},
                    "product_name": {"type": "string", "description": "产品名称（销售单必填）"},
                    "material_name": {"type": "string", "description": "物料名称（采购单必填）"},
                    "quantity": {"type": "number", "description": "数量"},
                    "unit_price": {"type": "number", "description": "单价"},
                    "order_date": {"type": "string", "description": "日期，默认为今天"},
                },
                "required": ["order_type"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_collection",
            "description": "创建收款单，用于记录客户回款并核销应收账款。",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string", "description": "客户名称"},
                    "amount": {"type": "number", "description": "收款金额"},
                    "collection_date": {"type": "string", "description": "收款日期，默认今天"},
                    "payment_method": {"type": "string", "description": "付款方式：TT/LC/DP等"},
                    "remark": {"type": "string", "description": "备注"},
                },
                "required": ["customer_name", "amount"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_payment",
            "description": "创建付款单，用于记录向供应商付款并核销应付账款。",
            "parameters": {
                "type": "object",
                "properties": {
                    "supplier_name": {"type": "string", "description": "供应商名称"},
                    "amount": {"type": "number", "description": "付款金额"},
                    "payment_date": {"type": "string", "description": "付款日期，默认今天"},
                    "payment_method": {"type": "string", "description": "付款方式"},
                    "remark": {"type": "string", "description": "备注"},
                },
                "required": ["supplier_name", "amount"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_purchase_invoice",
            "description": "录入采购发票，关联到采购订单。",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_no": {"type": "string", "description": "采购订单编号"},
                    "invoice_no": {"type": "string", "description": "发票号码"},
                    "amount": {"type": "number", "description": "发票金额"},
                    "invoice_date": {"type": "string", "description": "开票日期，默认今天"},
                },
                "required": ["order_no", "invoice_no", "amount"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_sales_invoice",
            "description": "录入销售发票，关联到销售订单。",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_no": {"type": "string", "description": "销售订单编号"},
                    "invoice_no": {"type": "string", "description": "发票号码"},
                    "amount": {"type": "number", "description": "发票金额"},
                    "invoice_date": {"type": "string", "description": "开票日期，默认今天"},
                },
                "required": ["order_no", "invoice_no", "amount"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_outsourcing",
            "description": "创建委外加工单：指定工序委外给某供应商加工，同时发出物料。",
            "parameters": {
                "type": "object",
                "properties": {
                    "production_order_no": {"type": "string", "description": "生产订单编号"},
                    "process_name": {"type": "string", "description": "委外的工序名称"},
                    "supplier_name": {"type": "string", "description": "委外供应商名称"},
                    "material_name": {"type": "string", "description": "发出的物料名称"},
                    "material_qty": {"type": "number", "description": "发出物料数量"},
                    "outsource_qty": {"type": "number", "description": "委外加工数量"},
                    "unit_price": {"type": "number", "description": "委外加工单价"},
                    "due_date": {"type": "string", "description": "要求完成日期"},
                },
                "required": ["production_order_no", "process_name", "supplier_name", "outsource_qty"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "issue_materials",
            "description": "生产领料/发料：为生产订单发出物料到产线或委外商。",
            "parameters": {
                "type": "object",
                "properties": {
                    "production_order_no": {"type": "string", "description": "生产订单编号"},
                    "material_name": {"type": "string", "description": "物料名称"},
                    "quantity": {"type": "number", "description": "发料数量"},
                    "warehouse_name": {"type": "string", "description": "仓库名称，不填用默认"},
                },
                "required": ["production_order_no", "material_name", "quantity"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "production_receipt",
            "description": "生产完工入库：将生产完成的成品入到成品仓。",
            "parameters": {
                "type": "object",
                "properties": {
                    "production_order_no": {"type": "string", "description": "生产订单编号"},
                    "quantity": {"type": "number", "description": "入库数量"},
                    "warehouse_name": {"type": "string", "description": "仓库名称，不填用默认成品仓"},
                    "receipt_date": {"type": "string", "description": "入库日期，默认今天"},
                },
                "required": ["production_order_no", "quantity"],
            },
        }
    },
]

SYSTEM_PROMPT = """你是 MTS 系统的 ERP 助手，通过对话帮助用户完成工作。

## 可用工具

1. query_entities — 查询：客户/供应商/物料/产品/应收/应付/发票清单
2. create_order — 创建采购订单/销售订单
3. create_collection — 创建收款单（客户回款）
4. create_payment — 创建付款单（向供应商付款）
5. create_purchase_invoice — 录入采购发票
6. create_sales_invoice — 录入销售发票
7. create_outsourcing — 创建委外加工单（工序委外+发料）
8. issue_materials — 生产发料/领料
9. production_receipt — 生产完工入库

## 工作流程

### 查询类
- 用户说「查xxx/找xxx/清单」→ 直接调 query_entities
- keyword 留空返回全部，填入关键词模糊搜索
- **不要编造数据**，一切以工具返回为准

### 创建类（三步确认）
第一步 — 问清要做什么操作（下单/收款/付款/发票/委外/发料/入库）
第二步 — 收集必要字段，缺什么问什么
第三步 — 逐项列出让用户核对，确认后再调工具
- 用户说「对/是/确认」再执行
- 执行失败时把错误原因告诉用户

## 对话风格
- 中文，简短，自然
- 一次只问一件事
- 不确定时反问，不要瞎猜"""


# ==================== 工具执行 ====================

ENTITY_LABELS = {
    "supplier": "供应商", "customer": "客户",
    "material": "物料", "product": "产品",
    "receivable": "应收账款", "payable": "应付账款",
    "purchase_invoice": "采购发票", "sales_invoice": "销售发票",
}


def _execute_query_entities(args: dict, db: Session) -> str:
    """执行 query_entities 工具"""
    from app.models.foundation import Supplier, Customer, Material, Product
    from app.models.sales import AccountsReceivable, SalesInvoice
    from app.models.purchase import AccountsPayable, PurchaseInvoice

    etype = args.get("entity_type")
    keyword = (args.get("keyword") or "").strip()

    FOUNDATION_MAP = {
        "supplier": (Supplier, Supplier.name, ["name", "code", "contact_person", "phone"]),
        "customer": (Customer, Customer.name_cn, ["name_cn", "code", "contact_person", "phone"]),
        "material": (Material, Material.name, ["name", "code", "unit", "spec"]),
        "product": (Product, Product.name_cn, ["name_cn", "code", "spec"]),
    }

    # 基础档案
    if etype in FOUNDATION_MAP:
        model_cls, name_col, fields = FOUNDATION_MAP[etype]
        q = db.query(model_cls).filter(model_cls.is_active == 1)
        if keyword:
            q = q.filter(name_col.like(f"%{keyword}%"))
        items = q.limit(100).all()
        label = ENTITY_LABELS.get(etype, etype)
        if not items:
            return f"未找到匹配的{label}" + (f"「{keyword}」" if keyword else "")
        lines = [f"📋 找到 {len(items)} 个{label}："]
        for item in items:
            parts = [f"**{getattr(item, fields[0], '')}**"]
            for f in fields[1:]:
                v = getattr(item, f, "") or ""
                if f == "code": v = f"`{v}`"
                parts.append(str(v))
            lines.append("  " + "｜".join(parts))
        return "\n".join(lines)

    # 应收账款
    if etype == "receivable":
        q = db.query(AccountsReceivable)
        if keyword:
            q = q.join(Customer).filter(Customer.name_cn.like(f"%{keyword}%"))
        items = q.order_by(AccountsReceivable.due_date).limit(50).all()
        if not items:
            return "暂无应收账款数据" if not keyword else f"未找到匹配的应收账款「{keyword}」"
        total = sum(i.balance for i in items)
        lines = [f"📋 应收账款（共 {len(items)} 笔，余额合计 ¥{total:,.2f}）："]
        for ar in items[:20]:
            cust_name = ""
            try:
                cust = db.query(Customer).filter(Customer.id == ar.customer_id).first()
                cust_name = cust.name_cn if cust else f"ID:{ar.customer_id}"
            except: pass
            lines.append(f"  {ar.ar_no}｜{cust_name}｜应收 ¥{ar.amount:,.2f}｜余额 ¥{ar.balance:,.2f}｜到期 {ar.due_date}")
        return "\n".join(lines)

    # 应付账款
    if etype == "payable":
        q = db.query(AccountsPayable)
        if keyword:
            q = q.join(Supplier).filter(Supplier.name.like(f"%{keyword}%"))
        items = q.order_by(AccountsPayable.due_date).limit(50).all()
        if not items:
            return "暂无应付账款数据" if not keyword else f"未找到匹配的应付账款「{keyword}」"
        total = sum(i.balance for i in items)
        lines = [f"📋 应付账款（共 {len(items)} 笔，余额合计 ¥{total:,.2f}）："]
        for ap in items[:20]:
            sup_name = ""
            try:
                sup = db.query(Supplier).filter(Supplier.id == ap.supplier_id).first()
                sup_name = sup.name if sup else f"ID:{ap.supplier_id}"
            except: pass
            lines.append(f"  {ap.ap_no}｜{sup_name}｜应付 ¥{ap.amount:,.2f}｜余额 ¥{ap.balance:,.2f}｜到期 {ap.due_date}")
        return "\n".join(lines)

    # 采购发票
    if etype == "purchase_invoice":
        q = db.query(PurchaseInvoice)
        if keyword:
            q = q.filter(PurchaseInvoice.invoice_no.like(f"%{keyword}%"))
        items = q.order_by(PurchaseInvoice.invoice_date.desc()).limit(50).all()
        if not items:
            return "暂无采购发票数据" if not keyword else f"未找到匹配的采购发票「{keyword}」"
        lines = [f"📋 采购发票（共 {len(items)} 张）："]
        for inv in items:
            lines.append(f"  {inv.invoice_no}｜¥{inv.amount:,.2f}｜{inv.invoice_date}｜{inv.status or '-'}")
        return "\n".join(lines)

    # 销售发票
    if etype == "sales_invoice":
        q = db.query(SalesInvoice)
        if keyword:
            q = q.filter(SalesInvoice.invoice_no.like(f"%{keyword}%"))
        items = q.order_by(SalesInvoice.invoice_date.desc()).limit(50).all()
        if not items:
            return "暂无销售发票数据" if not keyword else f"未找到匹配的销售发票「{keyword}」"
        lines = [f"📋 销售发票（共 {len(items)} 张）："]
        for inv in items:
            lines.append(f"  {inv.invoice_no}｜¥{inv.amount:,.2f}｜{inv.invoice_date}｜{inv.status or '-'}")
        return "\n".join(lines)

    return f"不支持的查询类型：{etype}"


def _execute_create_order(args: dict, db: Session) -> str:
    from app.models.foundation import Supplier, Customer, Material, Product
    otype = args.get("order_type")
    today = date.today().isoformat()
    try:
        if otype == "purchase_order":
            from app.models.purchase import PurchaseOrder, PurchaseOrderItem
            from app.utils.batch_no import generate_doc_no
            sup = db.query(Supplier).filter(Supplier.name.like(f"%{args['supplier_name']}%"), Supplier.is_active == 1).first()
            if not sup: return f"未找到供应商「{args['supplier_name']}」"
            mat = db.query(Material).filter(Material.name.like(f"%{args['material_name']}%"), Material.is_active == 1).first()
            if not mat: return f"未找到物料「{args['material_name']}」"
            qty, price = float(args.get("quantity", 0)), float(args.get("unit_price", 0))
            order_no = generate_doc_no(db, "PO")
            po = PurchaseOrder(order_no=order_no, supplier_id=sup.id, order_date=_parse_date(args.get("order_date", today)),
                               status="待审批", total_amount=round(qty * price, 2), tax_rate=13, remark="通过AI助手创建", created_by="AI")
            db.add(po); db.flush()
            db.add(PurchaseOrderItem(order_id=po.id, material_id=mat.id, quantity=qty, unit_price=price, total_amount=round(qty * price, 2), tax_rate=13))
            db.commit()
            return f"✅ **采购订单 {order_no} 已创建！**\n状态：待审批"
        elif otype == "sales_order":
            from app.models.sales import SalesOrder, SalesOrderItem
            from app.utils.batch_no import generate_doc_no
            cust = db.query(Customer).filter(Customer.name_cn.like(f"%{args['customer_name']}%"), Customer.is_active == 1).first()
            if not cust: cust = db.query(Customer).filter(Customer.name_en.like(f"%{args['customer_name']}%"), Customer.is_active == 1).first()
            if not cust: return f"未找到客户「{args['customer_name']}」"
            prod = db.query(Product).filter(Product.name_cn.like(f"%{args['product_name']}%"), Product.is_active == 1).first()
            if not prod: return f"未找到产品「{args['product_name']}」"
            qty, price = float(args.get("quantity", 0)), float(args.get("unit_price", 0))
            order_no = generate_doc_no(db, "SO")
            so = SalesOrder(order_no=order_no, customer_id=cust.id, order_date=_parse_date(args.get("order_date", today)),
                            status="待审核", total_amount=round(qty * price, 2), currency_id=1, exchange_rate=1, remark="通过AI助手创建", created_by="AI")
            db.add(so); db.flush()
            db.add(SalesOrderItem(order_id=so.id, product_id=prod.id, quantity=qty, unit_price=price, total_amount=round(qty * price, 2), tax_rate=13))
            db.commit()
            return f"✅ **销售订单 {order_no} 已创建！**\n状态：待审核"
        return f"不支持的单据类型：{otype}"
    except Exception as e:
        db.rollback()
        return f"❌ 创建失败：{e}"


def _execute_create_collection(args: dict, db: Session) -> str:
    """创建收款单 + 核销应收账款"""
    from app.models.foundation import Customer
    from app.models.sales import Collection, AccountsReceivable, CollectionAllocation
    from app.utils.batch_no import generate_doc_no

    try:
        cust = db.query(Customer).filter(Customer.name_cn.like(f"%{args['customer_name']}%"), Customer.is_active == 1).first()
        if not cust: return f"未找到客户「{args['customer_name']}」"

        amount = float(args["amount"])
        coll_no = generate_doc_no(db, "RC")
        coll = Collection(collection_no=coll_no, customer_id=cust.id, amount=amount, amount_fc=amount,
                          currency_id=1, exchange_rate=1, collection_date=_parse_date(args.get("collection_date", "")),
                          payment_method=args.get("payment_method", "TT"), operator="AI助手")
        db.add(coll); db.flush()

        # 自动核销：按到期日顺序核销
        ares = db.query(AccountsReceivable).filter(
            AccountsReceivable.customer_id == cust.id,
            AccountsReceivable.balance > 0,
        ).order_by(AccountsReceivable.due_date).all()
        remaining = amount
        allocated_lines = []
        for ar in ares:
            if remaining <= 0: break
            alloc = min(remaining, ar.balance)
            db.add(CollectionAllocation(collection_id=coll.id, ar_account_id=ar.id, allocated_amount=alloc))
            ar.balance -= alloc
            ar.collected_amount = (ar.collected_amount or 0) + alloc
            if ar.balance <= 0.001: ar.status = "已收款"
            elif ar.collected_amount > 0: ar.status = "部分收款"
            remaining -= alloc
            allocated_lines.append(f"    {ar.ar_no}：核销 ¥{alloc:,.2f}")
        db.commit()

        detail = "\n".join(allocated_lines)
        return f"✅ **收款单 {coll_no} 已创建！**\n收款金额：¥{amount:,.2f}\n核销明细：\n{detail}"
    except Exception as e:
        db.rollback()
        return f"❌ 创建收款单失败：{e}"


def _execute_create_payment(args: dict, db: Session) -> str:
    """创建付款单 + 核销应付账款"""
    from app.models.foundation import Supplier
    from app.models.purchase import Payment, AccountsPayable, PaymentAllocation
    from app.utils.batch_no import generate_doc_no

    try:
        sup = db.query(Supplier).filter(Supplier.name.like(f"%{args['supplier_name']}%"), Supplier.is_active == 1).first()
        if not sup: return f"未找到供应商「{args['supplier_name']}」"

        amount = float(args["amount"])
        pay_no = generate_doc_no(db, "PAY")
        pay = Payment(payment_no=pay_no, supplier_id=sup.id, amount=amount, amount_fc=amount,
                      currency_id=1, exchange_rate=1, payment_date=_parse_date(args.get("payment_date", "")),
                      payment_method=args.get("payment_method", "TT"), operator="AI助手")
        db.add(pay); db.flush()

        aps = db.query(AccountsPayable).filter(
            AccountsPayable.supplier_id == sup.id, AccountsPayable.balance > 0
        ).order_by(AccountsPayable.due_date).all()
        remaining = amount
        allocated_lines = []
        for ap in aps:
            if remaining <= 0: break
            alloc = min(remaining, ap.balance)
            db.add(PaymentAllocation(payment_id=pay.id, ap_account_id=ap.id, allocated_amount=alloc))
            ap.balance -= alloc
            ap.paid_amount = (ap.paid_amount or 0) + alloc
            if ap.balance <= 0.001: ap.status = "已付款"
            elif ap.paid_amount > 0: ap.status = "部分付款"
            remaining -= alloc
            allocated_lines.append(f"    {ap.ap_no}：核销 ¥{alloc:,.2f}")
        db.commit()

        detail = "\n".join(allocated_lines)
        return f"✅ **付款单 {pay_no} 已创建！**\n付款金额：¥{amount:,.2f}\n核销明细：\n{detail}"
    except Exception as e:
        db.rollback()
        return f"❌ 创建付款单失败：{e}"


def _execute_create_purchase_invoice(args: dict, db: Session) -> str:
    from app.models.purchase import PurchaseOrder, PurchaseInvoice
    from app.utils.batch_no import generate_doc_no
    try:
        order = db.query(PurchaseOrder).filter(PurchaseOrder.order_no == args["order_no"]).first()
        if not order: return f"未找到采购订单「{args['order_no']}」"
        inv = PurchaseInvoice(invoice_no=args["invoice_no"], order_id=order.id, supplier_id=order.supplier_id,
                              invoice_date=_parse_date(args.get("invoice_date", "")), amount=float(args["amount"]),
                              status="已开票")
        db.add(inv); db.commit()
        return f"✅ **采购发票 {args['invoice_no']} 已录入！**\n关联订单：{args['order_no']}"
    except Exception as e: return f"❌ 录入采购发票失败：{e}"


def _execute_create_sales_invoice(args: dict, db: Session) -> str:
    from app.models.sales import SalesOrder, SalesInvoice
    from app.utils.batch_no import generate_doc_no
    try:
        order = db.query(SalesOrder).filter(SalesOrder.order_no == args["order_no"]).first()
        if not order: return f"未找到销售订单「{args['order_no']}」"
        inv = SalesInvoice(invoice_no=args["invoice_no"], order_id=order.id, customer_id=order.customer_id,
                           invoice_date=_parse_date(args.get("invoice_date", "")), amount=float(args["amount"]),
                           tax_amount=0, total_amount=float(args["amount"]), status="已开票")
        db.add(inv); db.commit()
        return f"✅ **销售发票 {args['invoice_no']} 已录入！**\n关联订单：{args['order_no']}"
    except Exception as e: return f"❌ 录入销售发票失败：{e}"


def _execute_create_outsourcing(args: dict, db: Session) -> str:
    from app.models.foundation import Supplier, Material
    from app.models.production import ProductionOrder, OutsourcingOrder, MaterialIssueItem
    from app.utils.batch_no import generate_doc_no
    try:
        mo = db.query(ProductionOrder).filter(ProductionOrder.order_no == args["production_order_no"]).first()
        if not mo: return f"未找到生产订单「{args['production_order_no']}」"
        sup = db.query(Supplier).filter(Supplier.name.like(f"%{args['supplier_name']}%")).first()
        if not sup: return f"未找到供应商「{args['supplier_name']}」"

        os_no = generate_doc_no(db, "OS")
        oo = OutsourcingOrder(outsource_no=os_no, production_id=mo.id, outsourcer_id=sup.id,
                              product_id=mo.product_id, quantity=float(args["outsource_qty"]),
                              unit_price=float(args.get("unit_price", 0)),
                              total_amount=float(args.get("unit_price", 0)) * float(args["outsource_qty"]),
                              due_date=_parse_date(args.get("due_date", "")), status="待发料")
        db.add(oo); db.flush()

        # 如果有物料，同时发料
        mat_name = args.get("material_name", "")
        if mat_name:
            mat = db.query(Material).filter(Material.name.like(f"%{mat_name}%")).first()
            if mat and args.get("material_qty"):
                from datetime import datetime
                issue = MaterialIssueItem(issue_no=os_no, outsource_id=oo.id, material_id=mat.id,
                                          quantity=float(args["material_qty"]), issue_date=date.today(),
                                          operator="AI助手")
                db.add(issue)
                oo.material_status = "已发料"
        db.commit()
        return f"✅ **委外加工单 {os_no} 已创建！**\n供应商：{sup.name}\n加工数量：{args['outsource_qty']}"
    except Exception as e:
        db.rollback()
        return f"❌ 创建委外单失败：{e}"


def _execute_issue_materials(args: dict, db: Session) -> str:
    from app.models.foundation import Material, Warehouse
    from app.models.production import ProductionOrder, MaterialIssueItem
    try:
        mo = db.query(ProductionOrder).filter(ProductionOrder.order_no == args["production_order_no"]).first()
        if not mo: return f"未找到生产订单「{args['production_order_no']}」"
        mat = db.query(Material).filter(Material.name.like(f"%{args['material_name']}%")).first()
        if not mat: return f"未找到物料「{args['material_name']}」"

        issue = MaterialIssueItem(issue_no=f"IS-{date.today().isoformat()}", production_id=mo.id,
                                  material_id=mat.id, quantity=float(args["quantity"]),
                                  issue_date=date.today(), operator="AI助手")
        db.add(issue); db.commit()
        return f"✅ **已发料：{mat.name} × {args['quantity']}**\n生产订单：{args['production_order_no']}"
    except Exception as e:
        db.rollback()
        return f"❌ 发料失败：{e}"


def _execute_production_receipt(args: dict, db: Session) -> str:
    from app.models.foundation import Warehouse
    from app.models.production import ProductionOrder, ProductionReceipt, ProcessingInvoice
    from app.utils.batch_no import generate_doc_no
    try:
        mo = db.query(ProductionOrder).filter(ProductionOrder.order_no == args["production_order_no"]).first()
        if not mo: return f"未找到生产订单「{args['production_order_no']}」"

        rcp_no = generate_doc_no(db, "FG")
        rcp = ProductionReceipt(receipt_no=rcp_no, production_id=mo.id, product_id=mo.product_id,
                                quantity=float(args["quantity"]), receipt_date=_parse_date(args.get("receipt_date", "")),
                                operator="AI助手")
        db.add(rcp); db.commit()
        return f"✅ **完工入库单 {rcp_no} 已创建！**\n入库数量：{args['quantity']}\n生产订单：{args['production_order_no']}"
    except Exception as e:
        db.rollback()
        return f"❌ 入库失败：{e}"


def _parse_date(val):
    if val is None or isinstance(val, date):
        return val
    try: return date.fromisoformat(str(val)[:10])
    except (ValueError, TypeError): return date.today()


TOOL_EXECUTORS = {
    "query_entities": _execute_query_entities,
    "create_order": _execute_create_order,
    "create_collection": _execute_create_collection,
    "create_payment": _execute_create_payment,
    "create_purchase_invoice": _execute_create_purchase_invoice,
    "create_sales_invoice": _execute_create_sales_invoice,
    "create_outsourcing": _execute_create_outsourcing,
    "issue_materials": _execute_issue_materials,
    "production_receipt": _execute_production_receipt,
}


# ==================== AI 调用 ====================

def _call_llm(messages: list[dict], bot_config: BotConfig, tool_choice=None) -> dict | None:
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
        "max_tokens": bot_config.max_tokens or 4096,
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
    config = _get_config(db)
    if not config:
        return {"reply": "AI 未配置，请先在系统管理中配置 AI 模型", "state": "error", "history": history or []}

    messages = list(history or [])
    messages.append({"role": "user", "content": message})

    for _ in range(3):
        result = _call_llm(messages, config)
        if not result:
            return {"reply": "AI 调用失败", "state": "error", "history": history or []}

        choice = result["choices"][0]
        msg = choice["message"]

        if msg.get("content"):
            messages.append({"role": "assistant", "content": msg["content"]})
            if len(messages) > 20:
                messages = messages[-20:]
            return {"reply": msg["content"], "state": "idle", "history": messages}

        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                fn = tc["function"]
                name = fn["name"]
                try:
                    args = json.loads(fn["arguments"])
                except json.JSONDecodeError:
                    args = {}
                messages.append({
                    "role": "assistant",
                    "tool_calls": [{"id": tc["id"], "type": "function",
                                    "function": {"name": name, "arguments": fn["arguments"]}}],
                })
                executor = TOOL_EXECUTORS.get(name)
                tool_result = executor(args, db) if executor else f"未知工具：{name}"
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": tool_result})
            continue

        break

    return {"reply": "抱歉，我暂时无法处理这个请求", "state": "error", "history": history or []}


def _get_config(db: Session) -> BotConfig | None:
    config = db.query(BotConfig).filter(BotConfig.is_active == 1).first()
    if config and config.api_key:
        config.api_key = decrypt(config.api_key)
    return config
