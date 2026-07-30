"""
AI Agent — Function Calling 方案
=================================
LLM 通过工具函数操作 ERP。
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
            "description": "创建采购订单或销售订单，支持多个明细行一次创建。必须先确认所有字段后再调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_type": {"type": "string", "enum": ["purchase_order", "sales_order"], "description": "单据类型"},
                    "supplier_name": {"type": "string", "description": "供应商名称（采购单必填）"},
                    "customer_name": {"type": "string", "description": "客户名称（销售单必填）"},
                    "items": {
                        "type": "array",
                        "description": "订单明细行，支持多行一次创建",
                        "items": {
                            "oneOf": [
                                {
                                    "type": "object",
                                    "description": "采购明细：物料名称+数量+单价",
                                    "properties": {
                                        "material_name": {"type": "string", "description": "物料名称"},
                                        "quantity": {"type": "number", "description": "数量"},
                                        "unit_price": {"type": "number", "description": "单价"},
                                    },
                                    "required": ["material_name", "quantity", "unit_price"],
                                },
                                {
                                    "type": "object",
                                    "description": "销售明细：产品名称+数量+单价",
                                    "properties": {
                                        "product_name": {"type": "string", "description": "产品名称"},
                                        "quantity": {"type": "number", "description": "数量"},
                                        "unit_price": {"type": "number", "description": "单价"},
                                    },
                                    "required": ["product_name", "quantity", "unit_price"],
                                },
                            ],
                        },
                    },
                    "order_date": {"type": "string", "description": "日期，默认为今天"},
                },
                "required": ["order_type", "items"],
            },
        }
    },
    {
        "type": "function", "function": {
            "name": "create_collection",
            "description": "创建收款单，用于记录客户回款并核销应收账款。",
            "parameters": {"type": "object", "properties": {
                "customer_name": {"type": "string", "description": "客户名称"},
                "amount": {"type": "number", "description": "收款金额"},
                "collection_date": {"type": "string", "description": "收款日期，默认今天"},
                "payment_method": {"type": "string", "description": "付款方式：TT/LC/DP等"},
                "remark": {"type": "string", "description": "备注"},
            }, "required": ["customer_name", "amount"]},
        }
    },
    {
        "type": "function", "function": {
            "name": "create_payment",
            "description": "创建付款单，用于记录向供应商付款并核销应付账款。",
            "parameters": {"type": "object", "properties": {
                "supplier_name": {"type": "string", "description": "供应商名称"},
                "amount": {"type": "number", "description": "付款金额"},
                "payment_date": {"type": "string", "description": "付款日期，默认今天"},
                "payment_method": {"type": "string", "description": "付款方式"},
                "remark": {"type": "string", "description": "备注"},
            }, "required": ["supplier_name", "amount"]},
        }
    },
    {
        "type": "function", "function": {
            "name": "create_purchase_invoice",
            "description": "录入采购发票，关联到采购订单。",
            "parameters": {"type": "object", "properties": {
                "order_no": {"type": "string", "description": "采购订单编号"},
                "invoice_no": {"type": "string", "description": "发票号码"},
                "amount": {"type": "number", "description": "发票金额"},
                "invoice_date": {"type": "string", "description": "开票日期，默认今天"},
            }, "required": ["order_no", "invoice_no", "amount"]},
        }
    },
    {
        "type": "function", "function": {
            "name": "create_sales_invoice",
            "description": "录入销售发票，关联到销售订单。",
            "parameters": {"type": "object", "properties": {
                "order_no": {"type": "string", "description": "销售订单编号"},
                "invoice_no": {"type": "string", "description": "发票号码"},
                "amount": {"type": "number", "description": "发票金额"},
                "invoice_date": {"type": "string", "description": "开票日期，默认今天"},
            }, "required": ["order_no", "invoice_no", "amount"]},
        }
    },
    {
        "type": "function", "function": {
            "name": "create_outsourcing",
            "description": "创建委外加工单：指定工序委外给某供应商加工，同时发出物料。",
            "parameters": {"type": "object", "properties": {
                "production_order_no": {"type": "string", "description": "生产订单编号"},
                "process_name": {"type": "string", "description": "委外的工序名称"},
                "supplier_name": {"type": "string", "description": "委外供应商名称"},
                "material_name": {"type": "string", "description": "发出的物料名称"},
                "material_qty": {"type": "number", "description": "发出物料数量"},
                "outsource_qty": {"type": "number", "description": "委外加工数量"},
                "unit_price": {"type": "number", "description": "委外加工单价"},
                "due_date": {"type": "string", "description": "要求完成日期"},
            }, "required": ["production_order_no", "process_name", "supplier_name", "outsource_qty"]},
        }
    },
    {
        "type": "function", "function": {
            "name": "issue_materials",
            "description": "生产领料/发料：为生产订单发出物料到产线或委外商。",
            "parameters": {"type": "object", "properties": {
                "production_order_no": {"type": "string", "description": "生产订单编号"},
                "material_name": {"type": "string", "description": "物料名称"},
                "quantity": {"type": "number", "description": "发料数量"},
                "warehouse_name": {"type": "string", "description": "仓库名称，不填用默认"},
            }, "required": ["production_order_no", "material_name", "quantity"]},
        }
    },
    {
        "type": "function", "function": {
            "name": "production_receipt",
            "description": "生产完工入库：将生产完成的成品入到成品仓。",
            "parameters": {"type": "object", "properties": {
                "production_order_no": {"type": "string", "description": "生产订单编号"},
                "quantity": {"type": "number", "description": "入库数量"},
                "warehouse_name": {"type": "string", "description": "仓库名称，不填用默认成品仓"},
                "receipt_date": {"type": "string", "description": "入库日期，默认今天"},
            }, "required": ["production_order_no", "quantity"]},
        }
    },
]

SYSTEM_PROMPT = """你是 MTS 系统的 ERP 助手，通过对话帮助用户完成工作。

## 可用工具
1. query_entities — 查客户/供应商/物料/产品/应收/应付/发票清单
2. create_order — 创建采购订单/销售订单
3. create_collection — 创建收款单（客户回款+自动核销应收）
4. create_payment — 创建付款单（向供应商付款+自动核销应付）
5. create_purchase_invoice — 录入采购发票（关联采购单）
6. create_sales_invoice — 录入销售发票（关联销售单）
7. create_outsourcing — 创建委外加工单（工序委外+发料）
8. issue_materials — 生产发料/领料
9. production_receipt — 生产完工入库

## 工作流程

### 查询
- 用户说「查xxx/找xxx/xxx清单」→ **调 query_entities**
- keyword 留空 = 列出全部；有 keyword = 模糊搜索
- 应收/应付会自动汇总余额
- **不要编造数据**，工具返回什么就展示什么

### 创建类操作（三步确认）
第一步：问清要做什么
第二步：收集必要的字段，一次只问一个
第三步：逐项列出让用户核对，说「对/是/确认」再调工具

## 对话风格
- 中文，简短
- 一次只问一件事
- 不懂就反问"""


# ==================== 工具执行 ====================

ENTITY_LABELS = {
    "supplier": "供应商", "customer": "客户", "material": "物料", "product": "产品",
    "receivable": "应收账款", "payable": "应付账款",
    "purchase_invoice": "采购发票", "sales_invoice": "销售发票",
}


def _execute_query_entities(args: dict, db: Session) -> str:
    from app.models.foundation import Supplier, Customer, Material, Product
    from app.models.sales import AccountsReceivable, SalesInvoice
    from app.models.purchase import AccountsPayable, PurchaseInvoice

    etype, keyword = args.get("entity_type"), (args.get("keyword") or "").strip()

    if etype in {"supplier", "customer", "material", "product"}:
        FM = {"supplier": (Supplier, Supplier.name, ["name", "code", "contact_person", "phone", "tax_id", "payment_terms", "supplier_type"]),
              "customer": (Customer, Customer.name_cn, ["name_cn", "code", "contact_person", "phone", "email", "tax_id", "address", "payment_terms", "account_period"]),
              "material": (Material, Material.name, ["name", "code", "unit", "spec", "purchase_price"]),
              "product": (Product, Product.name_cn, ["name_cn", "code", "spec", "unit", "sale_price"])}
        mc, nc, fs = FM[etype]
        q = db.query(mc).filter(mc.is_active == 1)
        if keyword: q = q.filter(nc.like(f"%{keyword}%"))
        items = q.limit(100).all()
        label = ENTITY_LABELS.get(etype, etype)
        if not items: return f"未找到{label}" + (f"「{keyword}」" if keyword else "")
        lines = [f"📋 找到 {len(items)} 个{label}："]
        for it in items:
            parts = [f"**{getattr(it, fs[0], '')}**"]
            for f in fs[1:]:
                val = getattr(it, f, "") or ""
                if f == "code":
                    parts.append(f"`{val}`")
                elif isinstance(val, int) and f == "account_period":
                    parts.append(f"账期{val}天")
                elif isinstance(val, float):
                    parts.append(f"¥{val:,.2f}")
                else:
                    parts.append(str(val))
            lines.append("  " + "｜".join(parts))
        # 单条精确命中时展示更多详情
        if len(items) == 1 and keyword:
            it = items[0]
            extra = []
            if etype == "customer":
                extra.append(f"  付款条件: {it.payment_terms or '-'} | 账期: {it.account_period or 0}天 | 信用额度: ¥{it.credit_limit or 0:,.2f}")
                extra.append(f"  税号: {it.tax_id or '-'} | 地址: {it.address or '-'}")
            elif etype == "supplier":
                extra.append(f"  付款条件: {it.payment_terms or '-'} | 账期: {it.account_period or 0}天 | 供应范围: {it.supply_range or '-'}")
                extra.append(f"  税号: {it.tax_id or '-'} | 地址: {it.address or '-'}")
            elif etype == "material":
                extra.append(f"  价格: ¥{it.purchase_price or 0:,.2f} | 型号: {it.model or '-'}")
            elif etype == "product":
                extra.append(f"  价格: ¥{it.sale_price or 0:,.2f} | 型号: {it.model or '-'}")
            lines.extend(extra)
        return "\n".join(lines)

    if etype == "receivable":
        q = db.query(AccountsReceivable)
        if keyword: q = q.join(Customer).filter(Customer.name_cn.like(f"%{keyword}%"))
        items = q.order_by(AccountsReceivable.due_date).limit(50).all()
        if not items: return "暂无应收数据" if not keyword else f"未找到应收「{keyword}」"
        total = sum(i.balance for i in items)
        lines = [f"📋 应收账款（共{len(items)}笔，余额¥{total:,.2f}）："]
        for ar in items[:20]:
            cn = db.query(Customer).filter(Customer.id == ar.customer_id).first()
            lines.append(f"  {ar.ar_no}｜{cn.name_cn if cn else '-'}｜应收¥{ar.amount:,.2f}｜余额¥{ar.balance:,.2f}｜到期{ar.due_date}")
        return "\n".join(lines)

    if etype == "payable":
        q = db.query(AccountsPayable)
        if keyword: q = q.join(Supplier).filter(Supplier.name.like(f"%{keyword}%"))
        items = q.order_by(AccountsPayable.due_date).limit(50).all()
        if not items: return "暂无应付数据" if not keyword else f"未找到应付「{keyword}」"
        total = sum(i.balance for i in items)
        lines = [f"📋 应付账款（共{len(items)}笔，余额¥{total:,.2f}）："]
        for ap in items[:20]:
            sn = db.query(Supplier).filter(Supplier.id == ap.supplier_id).first()
            lines.append(f"  {ap.ap_no}｜{sn.name if sn else '-'}｜应付¥{ap.amount:,.2f}｜余额¥{ap.balance:,.2f}｜到期{ap.due_date}")
        return "\n".join(lines)

    if etype == "purchase_invoice":
        items = db.query(PurchaseInvoice).order_by(PurchaseInvoice.invoice_date.desc()).limit(50).all()
        if not items: return "暂无采购发票数据"
        lines = [f"📋 采购发票（共{len(items)}张）："]
        for i in items: lines.append(f"  {i.invoice_no}｜¥{i.amount:,.2f}｜{i.invoice_date}｜{i.status or '-'}")
        return "\n".join(lines)

    if etype == "sales_invoice":
        items = db.query(SalesInvoice).order_by(SalesInvoice.invoice_date.desc()).limit(50).all()
        if not items: return "暂无销售发票数据"
        lines = [f"📋 销售发票（共{len(items)}张）："]
        for i in items: lines.append(f"  {i.invoice_no}｜¥{i.amount:,.2f}｜{i.invoice_date}｜{i.status or '-'}")
        return "\n".join(lines)

    return f"不支持的类型：{etype}"


def _execute_create_order(args: dict, db: Session) -> str:
    from app.models.foundation import Supplier, Customer, Material, Product
    from app.utils.batch_no import generate_doc_no
    try:
        items = args.get("items", [])
        if not items:
            return "❌ 订单明细为空"

        if args["order_type"] == "purchase_order":
            from app.models.purchase import PurchaseOrder, PurchaseOrderItem
            sup = db.query(Supplier).filter(Supplier.name.like(f"%{args['supplier_name']}%")).first()
            if not sup: return f"未找到供应商「{args['supplier_name']}」"

            no = generate_doc_no(db, "PO")
            total_amt = 0
            po = PurchaseOrder(order_no=no, supplier_id=sup.id, order_date=_parse_date(args.get("order_date","")),
                               status="待审批", total_amount=0, tax_rate=13, remark="AI", created_by="AI")
            db.add(po); db.flush()

            lines = []
            for item in items:
                mat = db.query(Material).filter(Material.name.like(f"%{item['material_name']}%")).first()
                if not mat: return f"未找到物料「{item['material_name']}」"
                qty, pr = float(item.get("quantity",0)), float(item.get("unit_price",0))
                amt = round(qty * pr, 2)
                total_amt += amt
                db.add(PurchaseOrderItem(order_id=po.id, material_id=mat.id, quantity=qty, unit_price=pr, total_amount=amt, tax_rate=13))
                lines.append(f"  {mat.name} × {qty}{mat.unit} @ ¥{pr:.2f} = ¥{amt:,.2f}")

            po.total_amount = total_amt
            db.commit()
            return f"✅ 采购订单 {no} 已创建！共 {len(items)} 项\n" + "\n".join(lines)

        elif args["order_type"] == "sales_order":
            from app.models.sales import SalesOrder, SalesOrderItem
            cust = db.query(Customer).filter(Customer.name_cn.like(f"%{args['customer_name']}%")).first()
            if not cust: cust = db.query(Customer).filter(Customer.name_en.like(f"%{args['customer_name']}%")).first()
            if not cust: return f"未找到客户「{args['customer_name']}」"

            no = generate_doc_no(db, "SO")
            total_amt = 0
            so = SalesOrder(order_no=no, customer_id=cust.id, order_date=_parse_date(args.get("order_date","")),
                            status="待审核", total_amount=0, currency_id=1, exchange_rate=1, remark="AI", created_by="AI")
            db.add(so); db.flush()

            lines = []
            for item in items:
                prod = db.query(Product).filter(Product.name_cn.like(f"%{item['product_name']}%")).first()
                if not prod: return f"未找到产品「{item['product_name']}」"
                qty, pr = float(item.get("quantity",0)), float(item.get("unit_price",0))
                amt = round(qty * pr, 2)
                total_amt += amt
                db.add(SalesOrderItem(order_id=so.id, product_id=prod.id, quantity=qty, unit_price=pr, total_amount=amt, tax_rate=13))
                lines.append(f"  {prod.name_cn} × {qty}{prod.unit} @ ¥{pr:.2f} = ¥{amt:,.2f}")

            so.total_amount = total_amt
            db.commit()
            return f"✅ 销售订单 {no} 已创建！共 {len(items)} 项\n" + "\n".join(lines)

        return "❌ 未知订单类型"
    except Exception as e: db.rollback(); return f"❌ 创建失败：{e}"


def _execute_create_collection(args: dict, db: Session) -> str:
    from app.models.foundation import Customer
    from app.models.sales import Collection, AccountsReceivable, CollectionAllocation
    from app.utils.batch_no import generate_doc_no
    try:
        cust = db.query(Customer).filter(Customer.name_cn.like(f"%{args['customer_name']}%")).first()
        if not cust: return f"未找到客户「{args['customer_name']}」"
        amt = float(args["amount"]); cno = generate_doc_no(db, "RC")
        c = Collection(collection_no=cno, customer_id=cust.id, amount=amt, amount_fc=amt, currency_id=1, exchange_rate=1,
                       collection_date=_parse_date(args.get("collection_date","")), operator="AI")
        db.add(c); db.flush()
        remaining, lines = amt, []
        for ar in db.query(AccountsReceivable).filter(AccountsReceivable.customer_id==cust.id, AccountsReceivable.balance>0).order_by(AccountsReceivable.due_date).all():
            if remaining <= 0: break
            a = min(remaining, ar.balance)
            db.add(CollectionAllocation(collection_id=c.id, ar_account_id=ar.id, allocated_amount=a))
            ar.balance -= a; ar.collected_amount = (ar.collected_amount or 0) + a
            if ar.balance <= 0.001: ar.status = "已收款"
            elif ar.collected_amount > 0: ar.status = "部分收款"
            remaining -= a; lines.append(f"    {ar.ar_no}：¥{a:,.2f}")
        db.commit()
        return f"✅ 收款单 {cno} ¥{amt:,.2f}\n核销：\n" + "\n".join(lines)
    except Exception as e: db.rollback(); return f"❌ 收款失败：{e}"


def _execute_create_payment(args: dict, db: Session) -> str:
    from app.models.foundation import Supplier
    from app.models.purchase import Payment, AccountsPayable, PaymentAllocation
    from app.utils.batch_no import generate_doc_no
    try:
        sup = db.query(Supplier).filter(Supplier.name.like(f"%{args['supplier_name']}%")).first()
        if not sup: return f"未找到供应商「{args['supplier_name']}」"
        amt = float(args["amount"]); pno = generate_doc_no(db, "PAY")
        p = Payment(payment_no=pno, supplier_id=sup.id, amount=amt, amount_fc=amt, currency_id=1, exchange_rate=1,
                    payment_date=_parse_date(args.get("payment_date","")), operator="AI")
        db.add(p); db.flush()
        remaining, lines = amt, []
        for ap in db.query(AccountsPayable).filter(AccountsPayable.supplier_id==sup.id, AccountsPayable.balance>0).order_by(AccountsPayable.due_date).all():
            if remaining <= 0: break
            a = min(remaining, ap.balance)
            db.add(PaymentAllocation(payment_id=p.id, ap_account_id=ap.id, allocated_amount=a))
            ap.balance -= a; ap.paid_amount = (ap.paid_amount or 0) + a
            if ap.balance <= 0.001: ap.status = "已付款"
            elif ap.paid_amount > 0: ap.status = "部分付款"
            remaining -= a; lines.append(f"    {ap.ap_no}：¥{a:,.2f}")
        db.commit()
        return f"✅ 付款单 {pno} ¥{amt:,.2f}\n核销：\n" + "\n".join(lines)
    except Exception as e: db.rollback(); return f"❌ 付款失败：{e}"


def _execute_create_purchase_invoice(args: dict, db: Session) -> str:
    from app.models.purchase import PurchaseOrder, PurchaseInvoice
    try:
        o = db.query(PurchaseOrder).filter(PurchaseOrder.order_no==args["order_no"]).first()
        if not o: return f"未找到采购订单「{args['order_no']}」"
        db.add(PurchaseInvoice(invoice_no=args["invoice_no"], order_id=o.id, supplier_id=o.supplier_id,
                               invoice_date=_parse_date(args.get("invoice_date","")), amount=float(args["amount"]), status="已开票"))
        db.commit()
        return f"✅ 采购发票 {args['invoice_no']} 已录入"
    except Exception as e: return f"❌ 失败：{e}"


def _execute_create_sales_invoice(args: dict, db: Session) -> str:
    from app.models.sales import SalesOrder, SalesInvoice
    try:
        o = db.query(SalesOrder).filter(SalesOrder.order_no==args["order_no"]).first()
        if not o: return f"未找到销售订单「{args['order_no']}」"
        db.add(SalesInvoice(invoice_no=args["invoice_no"], order_id=o.id, customer_id=o.customer_id,
                            invoice_date=_parse_date(args.get("invoice_date","")), amount=float(args["amount"]),
                            tax_amount=0, total_amount=float(args["amount"]), status="已开票"))
        db.commit()
        return f"✅ 销售发票 {args['invoice_no']} 已录入"
    except Exception as e: return f"❌ 失败：{e}"


def _execute_create_outsourcing(args: dict, db: Session) -> str:
    from app.models.foundation import Supplier, Material
    from app.models.production import ProductionOrder, OutsourcingOrder, MaterialIssueItem
    from app.utils.batch_no import generate_doc_no
    try:
        mo = db.query(ProductionOrder).filter(ProductionOrder.order_no==args["production_order_no"]).first()
        if not mo: return f"未找到生产订单「{args['production_order_no']}」"
        sup = db.query(Supplier).filter(Supplier.name.like(f"%{args['supplier_name']}%")).first()
        if not sup: return f"未找到供应商「{args['supplier_name']}」"
        os_no = generate_doc_no(db, "OS")
        oo = OutsourcingOrder(outsource_no=os_no, production_id=mo.id, outsourcer_id=sup.id, product_id=mo.product_id,
                              quantity=float(args["outsource_qty"]), unit_price=float(args.get("unit_price",0)),
                              total_amount=float(args.get("unit_price",0))*float(args["outsource_qty"]),
                              due_date=_parse_date(args.get("due_date","")), status="待发料")
        db.add(oo); db.flush()
        if args.get("material_name"):
            mat = db.query(Material).filter(Material.name.like(f"%{args['material_name']}%")).first()
            if mat and args.get("material_qty"):
                db.add(MaterialIssueItem(issue_no=os_no, outsource_id=oo.id, material_id=mat.id, quantity=float(args["material_qty"]), operator="AI"))
                oo.material_status = "已发料"
        db.commit()
        return f"✅ 委外单 {os_no}（{sup.name}）"
    except Exception as e: db.rollback(); return f"❌ 委外失败：{e}"


def _execute_issue_materials(args: dict, db: Session) -> str:
    from app.models.foundation import Material
    from app.models.production import ProductionOrder, MaterialIssueItem
    try:
        mo = db.query(ProductionOrder).filter(ProductionOrder.order_no==args["production_order_no"]).first()
        if not mo: return f"未找到生产订单「{args['production_order_no']}」"
        mat = db.query(Material).filter(Material.name.like(f"%{args['material_name']}%")).first()
        if not mat: return f"未找到物料「{args['material_name']}」"
        db.add(MaterialIssueItem(issue_no=f"IS-{date.today()}", production_id=mo.id, material_id=mat.id,
                                 quantity=float(args["quantity"]), issue_date=date.today(), operator="AI"))
        db.commit()
        return f"✅ 已发料：{mat.name} × {args['quantity']}"
    except Exception as e: db.rollback(); return f"❌ 发料失败：{e}"


def _execute_production_receipt(args: dict, db: Session) -> str:
    from app.models.production import ProductionOrder, ProductionReceipt
    from app.utils.batch_no import generate_doc_no
    try:
        mo = db.query(ProductionOrder).filter(ProductionOrder.order_no==args["production_order_no"]).first()
        if not mo: return f"未找到生产订单「{args['production_order_no']}」"
        rc = generate_doc_no(db, "FG")
        db.add(ProductionReceipt(receipt_no=rc, production_id=mo.id, product_id=mo.product_id,
                                  quantity=float(args["quantity"]), receipt_date=_parse_date(args.get("receipt_date","")), operator="AI"))
        db.commit()
        return f"✅ 入库单 {rc}（{args['quantity']}个）"
    except Exception as e: db.rollback(); return f"❌ 入库失败：{e}"


def _parse_date(val):
    if val is None or isinstance(val, date): return val
    try: return date.fromisoformat(str(val)[:10])
    except: return date.today()


TOOL_EXECUTORS = {k: globals()[f"_execute_{k}"] for k in
    ["query_entities", "create_order", "create_collection", "create_payment",
     "create_purchase_invoice", "create_sales_invoice", "create_outsourcing",
     "issue_materials", "production_receipt"]}


# ==================== AI 调用 ====================

def _call_llm(messages: list[dict], bot_config: BotConfig, api_key: str) -> dict | None:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    base_url = (bot_config.base_url or "").rstrip("/") or (
        "https://api.deepseek.com" if bot_config.provider == "deepseek" else "https://api.openai.com"
    )
    payload = {
        "model": bot_config.model or "deepseek-chat",
        "messages": [{"role": "system", "content": bot_config.system_prompt or SYSTEM_PROMPT}] + messages,
        "temperature": bot_config.temperature or 0.1,
        "max_tokens": bot_config.max_tokens or 8192,
        "tools": TOOLS,
        "tool_choice": "auto",
    }
    try:
        with httpx.Client(timeout=120) as client:
            resp = client.post(f"{base_url}/v1/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        import logging
        logger = logging.getLogger("ai_chat")
        detail = e.response.text[:500] if e.response else str(e)
        # 调试：打印当前 messages 中的 tool 角色数量
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        toolcall_msgs = [m for m in messages if m.get("tool_calls")]
        logger.error(f"LLM 400: {detail}")
        logger.error(f"DEBUG: tool_msgs={len(tool_msgs)}, toolcall_msgs={len(toolcall_msgs)}, total_msgs={len(messages)}")
        if tool_msgs and toolcall_msgs:
            last_tc = toolcall_msgs[-1]
            last_tool = tool_msgs[-1]
            tc_ids = [tc["id"] for tc in last_tc.get("tool_calls", [])]
            logger.error(f"DEBUG: last assistant tool_call ids={tc_ids}, last tool id={last_tool.get('tool_call_id')}")
            if last_tool.get("tool_call_id") not in tc_ids:
                logger.error("DEBUG: ⚠️ MISMATCH — tool_call_id not in preceding assistant tool_calls!")
        return None
    except Exception as e:
        import logging
        logging.getLogger("ai_chat").error(f"LLM call failed: {e}")
        return None


# ==================== 主流程 ====================

def process_message(message: str, history: list[dict], db: Session) -> dict:
    config = _get_config(db)
    if not config:
        return {"reply": "AI 未配置", "state": "error", "history": history or []}
    api_key = _get_api_key(config)
    if not api_key:
        return {"reply": "API Key 未配置或解密失败", "state": "error", "history": history or []}

    messages = list(history or [])
    messages.append({"role": "user", "content": message})

    for _ in range(3):
        result = _call_llm(messages, config, api_key)
        if not result:
            return {"reply": "AI 调用失败，请稍后重试或检查 AI 模型配置", "state": "error", "history": history or []}

        choice = result["choices"][0]
        msg = choice["message"]

        # 优先处理 tool_calls（DeepSeek 可能同时返回 content + tool_calls）
        if msg.get("tool_calls"):
            # 构建一条 assistant 消息，包含本次返回的全部 tool_calls
            tool_calls_sanitized = []
            for tc in msg["tool_calls"]:
                tc_sanitized = {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"],
                    },
                }
                tool_calls_sanitized.append(tc_sanitized)
            assistant_msg = {"role": "assistant", "tool_calls": tool_calls_sanitized}
            if msg.get("content"):
                assistant_msg["content"] = msg["content"]
            messages.append(assistant_msg)

            # 逐个执行工具，追加 tool 结果
            for tc in msg["tool_calls"]:
                fn = tc["function"]
                name = fn["name"]
                try:
                    args = json.loads(fn["arguments"])
                except:
                    args = {}

                executor = TOOL_EXECUTORS.get(name)
                tool_result = executor(args, db) if executor else f"未知工具：{name}"
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": tool_result})
            continue

        if msg.get("content"):
            messages.append({"role": "assistant", "content": msg["content"]})
            # 安全截断：保留完整对话轮次，不拆分 tool_calls↔tool 配对
            if len(messages) > 12:
                # 找到第12条消息的位置
                cutoff = len(messages) - 12
                # 检查从 cutoff 开始的第一个消息如果是 tool，需要把 preceding tool_calls 也包含进来
                for i in range(cutoff, len(messages)):
                    m = messages[i]
                    if m.get("role") == "tool":
                        # 这条 tool 没有对应的 tool_calls 了，需要往前找
                        offset = i
                        # 从 offset 往前找最近的 assistant(tool_calls)
                        for j in range(offset - 1, -1, -1):
                            if messages[j].get("tool_calls"):
                                cutoff = j
                                break
                        break
                    elif m.get("tool_calls"):
                        # 如果从 cutoff 开始就是 tool_calls，保留这条及其后的所有 tool
                        break
                    else:
                        # user 或 assistant(content)，跳过
                        pass
                messages = messages[cutoff:]
            return {"reply": msg["content"], "state": "idle", "history": messages}

        break

    return {"reply": "抱歉，我暂时无法处理", "state": "error", "history": history or []}

def _get_config(db: Session) -> BotConfig | None:
    """获取启用的 AI 配置"""
    return db.query(BotConfig).filter(BotConfig.is_active == 1).first()


def _get_api_key(config: BotConfig) -> str:
    """解密 API Key，不修改原对象"""
    if config and config.api_key:
        return decrypt(config.api_key)
    return ""
