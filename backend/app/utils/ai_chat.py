"""
AI Agent — Function Calling 方案
=================================
LLM 通过工具函数操作 ERP。
"""

import json
import httpx
from datetime import date
from pathlib import Path
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
            "name": "issue_materials",
            "description": "生产领料/发料：为生产订单（纯自产）发出物料到产线。",
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
    {
        "type": "function", "function": {
            "name": "query_inventory",
            "description": "查询当前库存：按物料/产品名称或仓库查看库存数量与批次。",
            "parameters": {"type": "object", "properties": {
                "keyword": {"type": "string", "description": "物料或产品名称关键词，留空列出全部"},
                "warehouse_name": {"type": "string", "description": "仓库名称，不填查全部仓库"},
            }},
        }
    },
    {
        "type": "function", "function": {
            "name": "query_pending_approvals",
            "description": "列出当前用户可见的待审核单据（采购订单/销售订单）。",
            "parameters": {"type": "object", "properties": {
                "order_type": {"type": "string", "enum": ["purchase_order", "sales_order"],
                               "description": "单据类型，留空列出全部"},
            }},
        }
    },
    {
        "type": "function", "function": {
            "name": "approve_order",
            "description": "审核单据：采购订单（待审核→已审核）或销售订单（待审核→已审，不自动生成生产订单）。审核后明细行可转直采/转外发(委外)/转生产(自产)。必须先列出单据让用户指定再调用。",
            "parameters": {"type": "object", "properties": {
                "order_type": {"type": "string", "enum": ["purchase_order", "sales_order"], "description": "单据类型"},
                "order_no": {"type": "string", "description": "单据编号，如 PO-xxx / SO-xxx"},
            }, "required": ["order_type", "order_no"]},
        }
    },
    {
        "type": "function", "function": {
            "name": "unapprove_order",
            "description": "反审核采购订单（已审核→待审核）。无下游入库/发票时才允许；销售订单不支持反审核。",
            "parameters": {"type": "object", "properties": {
                "order_type": {"type": "string", "enum": ["purchase_order"], "description": "单据类型"},
                "order_no": {"type": "string", "description": "采购订单编号"},
            }, "required": ["order_type", "order_no"]},
        }
    },
    {
        "type": "function", "function": {
            "name": "query_manual",
            "description": "查询系统操作手册：按关键词返回对应操作章节（如「如何录入客户」「采购入库怎么操作」）。",
            "parameters": {"type": "object", "properties": {
                "keyword": {"type": "string", "description": "搜索关键词，如：客户/采购入库/收款/审核"},
            }, "required": ["keyword"]},
        }
    },
]

SYSTEM_PROMPT = """你是 MTS 系统的 ERP 助手（Matsu），通过对话帮助用户完成工作。

## 可用工具
1. query_entities — 查客户/供应商/物料/产品/应收/应付/发票清单
2. query_inventory — 查当前库存（按名称/仓库）
3. query_pending_approvals — 列待审核单据
4. approve_order / unapprove_order — 审核/反审核单据
5. create_order — 创建采购订单/销售订单
6. create_collection — 创建收款单（客户回款+自动核销应收）
7. create_payment — 创建付款单（向供应商付款+自动核销应付）
8. create_purchase_invoice / create_sales_invoice — 录入发票
9. issue_materials — 生产发料/领料
10. production_receipt — 生产完工入库
11. query_manual — 查系统操作手册（教用户怎么操作）

## 权限规则
- 系统已按用户权限过滤工具，只使用提供的工具
- 用户没有权限的操作，直接说明「您没有该操作的权限」，不要尝试调用

## 工作流程

### 查询
- 用户说「查xxx/找xxx/xxx清单」→ 调 query_entities 或 query_inventory
- keyword 留空 = 列出全部；有 keyword = 模糊搜索
- 应收/应付会自动汇总余额
- **不要编造数据**，工具返回什么就展示什么
- 用户问「怎么操作/怎么录/怎么审核」→ 调 query_manual

### 审核类操作（先查后审）
第一步：用户说「审核/审批」时，先调 query_pending_approvals 列出待审核单据
第二步：让用户指定单据号（如 PO-20260731-001）
第三步：确认后调 approve_order，核对返回结果

- 销售订单审核**不会生成生产订单**；审核通过后明细行处于「未生产」，用户需为每行选择三条独立路线之一：
  - **转直采**：进入「采购管理→销售订单转采购」办理采购
  - **转外发**：进入「委外管理→销售订单转委外」办理委外（委外=outsource）
  - **转生产**：转为自产，生成生产订单（纯自产=production）
  三者互斥，按业务实际选择，不要替用户假设路线。用户说「转外发/委外」指转外发路线，「转生产/自产/生产」指转生产路线。

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


def _operator_name(user) -> str:
    """操作人显示名（AI 工具调用兜底）"""
    if user is None:
        return "AI"
    return user.display_name or user.username


def _execute_query_entities(args: dict, db: Session, user=None) -> str:
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


def _execute_create_order(args: dict, db: Session, user=None) -> str:
    from app.models.foundation import Supplier, Customer, Material, Product
    from app.utils.batch_no import generate_doc_no
    operator = _operator_name(user)
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
                               status="待审核", total_amount=0, tax_rate=13, remark="AI", created_by=operator)
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
                            status="待审核", total_amount=0, currency_id=1, exchange_rate=1, remark="AI", created_by=operator)
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


def _execute_create_collection(args: dict, db: Session, user=None) -> str:
    from app.models.foundation import Customer
    from app.models.sales import Collection, AccountsReceivable, CollectionAllocation
    from app.utils.batch_no import generate_doc_no
    try:
        cust = db.query(Customer).filter(Customer.name_cn.like(f"%{args['customer_name']}%")).first()
        if not cust: return f"未找到客户「{args['customer_name']}」"
        amt = float(args["amount"]); cno = generate_doc_no(db, "CR")
        c = Collection(collection_no=cno, customer_id=cust.id, amount=amt, amount_fc=amt, currency_id=1, exchange_rate=1,
                       collection_date=_parse_date(args.get("collection_date","")), operator=_operator_name(user))
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


def _execute_create_payment(args: dict, db: Session, user=None) -> str:
    from app.models.foundation import Supplier
    from app.models.purchase import Payment, AccountsPayable, PaymentAllocation
    from app.utils.batch_no import generate_doc_no
    try:
        sup = db.query(Supplier).filter(Supplier.name.like(f"%{args['supplier_name']}%")).first()
        if not sup: return f"未找到供应商「{args['supplier_name']}」"
        amt = float(args["amount"]); pno = generate_doc_no(db, "PM")
        p = Payment(payment_no=pno, supplier_id=sup.id, amount=amt, amount_fc=amt, currency_id=1, exchange_rate=1,
                    payment_date=_parse_date(args.get("payment_date","")), operator=_operator_name(user))
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


def _execute_create_purchase_invoice(args: dict, db: Session, user=None) -> str:
    from app.models.purchase import PurchaseOrder, PurchaseInvoice
    try:
        o = db.query(PurchaseOrder).filter(PurchaseOrder.order_no==args["order_no"]).first()
        if not o: return f"未找到采购订单「{args['order_no']}」"
        db.add(PurchaseInvoice(invoice_no=args["invoice_no"], order_id=o.id, supplier_id=o.supplier_id,
                               invoice_date=_parse_date(args.get("invoice_date","")), amount=float(args["amount"]), status="已开票"))
        db.commit()
        return f"✅ 采购发票 {args['invoice_no']} 已录入"
    except Exception as e: return f"❌ 失败：{e}"


def _execute_create_sales_invoice(args: dict, db: Session, user=None) -> str:
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


def _execute_issue_materials(args: dict, db: Session, user=None) -> str:
    from app.models.foundation import Material
    from app.models.production import ProductionOrder, MaterialIssueItem
    try:
        mo = db.query(ProductionOrder).filter(ProductionOrder.order_no==args["production_order_no"]).first()
        if not mo: return f"未找到生产订单「{args['production_order_no']}」"
        mat = db.query(Material).filter(Material.name.like(f"%{args['material_name']}%")).first()
        if not mat: return f"未找到物料「{args['material_name']}」"
        db.add(MaterialIssueItem(issue_no=f"IS-{date.today()}", production_id=mo.id, material_id=mat.id,
                                 quantity=float(args["quantity"]), issue_date=date.today(), operator=_operator_name(user)))
        db.commit()
        return f"✅ 已发料：{mat.name} × {args['quantity']}"
    except Exception as e: db.rollback(); return f"❌ 发料失败：{e}"


def _execute_production_receipt(args: dict, db: Session, user=None) -> str:
    from app.models.production import ProductionOrder, ProductionReceipt
    from app.utils.batch_no import generate_doc_no
    try:
        mo = db.query(ProductionOrder).filter(ProductionOrder.order_no==args["production_order_no"]).first()
        if not mo: return f"未找到生产订单「{args['production_order_no']}」"
        rc = generate_doc_no(db, "FG")
        db.add(ProductionReceipt(receipt_no=rc, production_id=mo.id, product_id=mo.product_id,
                                  quantity=float(args["quantity"]), receipt_date=_parse_date(args.get("receipt_date","")), operator=_operator_name(user)))
        db.commit()
        return f"✅ 入库单 {rc}（{args['quantity']}个）"
    except Exception as e: db.rollback(); return f"❌ 入库失败：{e}"


def _execute_query_inventory(args: dict, db: Session, user=None) -> str:
    """查库存：按名称关键词 + 仓库，按 物料/产品+仓库 汇总"""
    from app.models.inventory import WarehouseInventory
    from app.models.foundation import Material, Product, Warehouse
    from collections import defaultdict

    keyword = (args.get("keyword") or "").strip()
    wh_name = (args.get("warehouse_name") or "").strip()

    wh = None
    if wh_name:
        wh = db.query(Warehouse).filter(Warehouse.name.like(f"%{wh_name}%")).first()
        if not wh:
            return f"未找到仓库「{wh_name}」"

    q = db.query(WarehouseInventory)
    if wh:
        q = q.filter(WarehouseInventory.warehouse_id == wh.id)
    rows = q.all()

    if keyword:
        mat_ids = {m.id for m in db.query(Material).filter(Material.name.like(f"%{keyword}%")).all()}
        prod_ids = {p.id for p in db.query(Product).filter(Product.name_cn.like(f"%{keyword}%")).all()}
        rows = [r for r in rows if r.material_id in mat_ids or r.product_id in prod_ids]

    if not rows:
        return "没有找到库存记录" + (f"「{keyword}」" if keyword else "")

    agg = defaultdict(lambda: {"qty": 0, "batches": 0})
    for r in rows:
        key = (r.material_id, r.product_id, r.warehouse_id)
        agg[key]["qty"] += r.quantity or 0
        agg[key]["batches"] += 1

    wh_cache, mat_cache, prod_cache = {}, {}, {}
    lines = [f"📦 库存（{len(agg)} 项）："]
    for (mid, pid, wid), v in list(agg.items())[:50]:
        if wid not in wh_cache:
            w = db.query(Warehouse).filter(Warehouse.id == wid).first()
            wh_cache[wid] = w.name if w else "-"
        name, unit = "-", ""
        if mid:
            if mid not in mat_cache:
                m = db.query(Material).filter(Material.id == mid).first()
                mat_cache[mid] = (m.name if m else "-", m.unit if m else "")
            name, unit = mat_cache[mid]
        elif pid:
            if pid not in prod_cache:
                p = db.query(Product).filter(Product.id == pid).first()
                prod_cache[pid] = (p.name_cn if p else "-", p.unit if p else "")
            name, unit = prod_cache[pid]
        lines.append(f"  **{name}**｜{wh_cache[wid]}｜{v['qty']:g}{unit}｜{v['batches']}个批次")
    return "\n".join(lines)


def _execute_query_pending_approvals(args: dict, db: Session, user=None) -> str:
    """列待审核单据（按用户权限过滤可见类型）"""
    from app.models.purchase import PurchaseOrder
    from app.models.sales import SalesOrder
    from app.models.foundation import Supplier, Customer

    otype = args.get("order_type")
    can_po = user is not None and user.has_permission("menu:purchase:orders")
    can_so = user is not None and user.has_permission("menu:sales:orders")

    lines = []
    if otype in (None, "purchase_order") and can_po:
        pos = db.query(PurchaseOrder).filter(PurchaseOrder.status == "待审核").limit(20).all()
        for po in pos:
            sup = db.query(Supplier).filter(Supplier.id == po.supplier_id).first()
            lines.append(f"  **{po.order_no}**｜{sup.name if sup else '-'}｜¥{po.total_amount or 0:,.2f}｜{po.order_date}")
    if otype in (None, "sales_order") and can_so:
        sos = db.query(SalesOrder).filter(SalesOrder.status == "待审核").limit(20).all()
        for so in sos:
            c = db.query(Customer).filter(Customer.id == so.customer_id).first()
            lines.append(f"  **{so.order_no}**｜{c.name_cn if c else '-'}｜¥{so.total_amount or 0:,.2f}｜{so.order_date}")

    if not lines:
        if not (can_po or can_so):
            return "您没有待审核单据的查看权限"
        return "没有待审核的单据" + ("" if not otype else "（该类型）")
    return "📋 待审核单据：\n" + "\n".join(lines)


def _execute_approve_order(args: dict, db: Session, user=None) -> str:
    from app.models.purchase import PurchaseOrder
    from app.models.sales import SalesOrder

    no = (args.get("order_no") or "").strip()
    otype = args.get("order_type")
    if not no:
        return "❌ 缺少单据编号"
    try:
        if otype == "purchase_order":
            o = db.query(PurchaseOrder).filter(PurchaseOrder.order_no == no).first()
            if not o: return f"未找到采购订单「{no}」"
            if o.status != "待审核": return f"订单 {no} 当前状态「{o.status}」，不能审核"
            o.status = "已审核"
            db.commit()
            return f"✅ 采购订单 {no} 已审核"
        elif otype == "sales_order":
            o = db.query(SalesOrder).filter(SalesOrder.order_no == no).first()
            if not o: return f"未找到销售订单「{no}」"
            if o.status != "待审核": return f"订单 {no} 当前状态「{o.status}」，不能审核"
            o.status = "已审"
            # 与 UI 销售审核一致（SP 流程）：审核不自动生成生产订单，仅初始化明细行生产状态；
            # 明细行后续由用户选择转直采 / 转外发(委外) / 转生产(自产) 三条独立路线。
            for item in o.items:
                if item.production_status in (None, "", "未生产"):
                    item.production_status = "未生产"
            db.commit()
            return f"✅ 销售订单 {no} 已审核。明细行待处理，请选择：转直采 / 转外发(委外) / 转生产(自产)。"
        return "❌ 未知订单类型"
    except Exception as e:
        db.rollback()
        return f"❌ 审核失败：{e}"


def _execute_unapprove_order(args: dict, db: Session, user=None) -> str:
    from app.models.purchase import PurchaseOrder, PurchaseReceipt, PurchaseInvoice

    no = (args.get("order_no") or "").strip()
    otype = args.get("order_type")
    if otype != "purchase_order":
        return "仅采购订单支持反审核"
    if not no:
        return "❌ 缺少单据编号"
    try:
        o = db.query(PurchaseOrder).filter(PurchaseOrder.order_no == no).first()
        if not o: return f"未找到采购订单「{no}」"
        if o.status != "已审核": return f"订单 {no} 当前状态「{o.status}」，不能反审核"
        if db.query(PurchaseReceipt).filter(PurchaseReceipt.order_id == o.id).count() > 0:
            return f"订单 {no} 已有关联入库单，无法反审核"
        if db.query(PurchaseInvoice).filter(PurchaseInvoice.order_id == o.id).count() > 0:
            return f"订单 {no} 已有关联发票，无法反审核"
        o.status = "待审核"
        db.commit()
        return f"✅ 采购订单 {no} 已反审核"
    except Exception as e:
        db.rollback()
        return f"❌ 反审核失败：{e}"


# ==================== 操作手册检索 ====================

MANUAL_PATH = Path(__file__).resolve().parents[3] / "docs" / "operations-manual.md"
_manual_cache: dict = {"mtime": None, "sections": []}


def _load_manual_sections() -> list:
    """按 ## 标题切分操作手册为章节，mtime 变化时重新加载"""
    try:
        mtime = MANUAL_PATH.stat().st_mtime
    except OSError:
        return []
    if _manual_cache["mtime"] == mtime:
        return _manual_cache["sections"]
    try:
        text = MANUAL_PATH.read_text(encoding="utf-8")
    except OSError:
        return []
    sections, cur_title, cur_lines = [], None, []
    for line in text.splitlines():
        if line.startswith("## "):
            if cur_title:
                sections.append((cur_title, "\n".join(cur_lines)))
            cur_title = line[3:].strip()
            cur_lines = []
        elif cur_title is not None:
            cur_lines.append(line)
    if cur_title:
        sections.append((cur_title, "\n".join(cur_lines)))
    _manual_cache.update(mtime=mtime, sections=sections)
    return sections


def _execute_query_manual(args: dict, db: Session, user=None) -> str:
    """查操作手册：标题命中加权 3，正文命中加权 1，返回 Top3 章节节选"""
    keyword = (args.get("keyword") or "").strip()
    if not keyword:
        return "请提供搜索关键词，例如「采购入库怎么操作」"
    sections = _load_manual_sections()
    if not sections:
        return "操作手册暂不可用，请稍后再试"
    hits = []
    for title, body in sections:
        score = 0
        if keyword in title:
            score += 3
        score += body.count(keyword)
        if score:
            hits.append((score, title, body))
    hits.sort(key=lambda x: -x[0])
    if not hits:
        return f"手册中未找到与「{keyword}」相关的内容"
    lines = [f"📖 操作手册（找到 {len(hits)} 节）："]
    for score, title, body in hits[:3]:
        # 取关键词附近片段
        idx = body.find(keyword)
        start = max(0, idx - 80)
        snippet = body[start:start + 300].replace("\n", " ").strip()
        lines.append(f"\n**{title}**\n  …{snippet}…")
    return "\n".join(lines)


def _parse_date(val):
    if val is None or isinstance(val, date): return val
    try: return date.fromisoformat(str(val)[:10])
    except: return date.today()


# ==================== 权限映射 ====================

# 工具 → 所需菜单权限码。dict 表示按子类型（entity_type/order_type）分别校验；None 表示所有登录用户可用
TOOL_PERMS = {
    "query_entities": {
        "customer": "menu:customers", "supplier": "menu:suppliers",
        "material": "menu:materials", "product": "menu:products",
        "receivable": "menu:sales:ar", "payable": "menu:purchase:ap",
        "purchase_invoice": "menu:purchase:invoices", "sales_invoice": "menu:sales:invoices",
    },
    "create_order": {"purchase_order": "menu:purchase:orders", "sales_order": "menu:sales:orders"},
    "create_collection": "menu:sales:collections",
    "create_payment": "menu:purchase:payments",
    "create_purchase_invoice": "menu:purchase:invoices",
    "create_sales_invoice": "menu:sales:invoices",
    "issue_materials": "menu:production:orders",
    "production_receipt": "menu:production:orders",
    "query_inventory": "menu:inventory",
    "query_pending_approvals": None,  # 内部按权限过滤可见单据
    "approve_order": {"purchase_order": "menu:purchase:orders", "sales_order": "menu:sales:orders"},
    "unapprove_order": {"purchase_order": "menu:purchase:orders"},
    "query_manual": None,
}

# 写操作工具（需要记审计日志）
AUDIT_TOOLS = {
    "create_order", "create_collection", "create_payment",
    "create_purchase_invoice", "create_sales_invoice",
    "issue_materials", "production_receipt",
    "approve_order", "unapprove_order",
}


def _allowed_subtypes(user, rule: dict) -> list:
    """返回用户有权限的子类型列表（如 order_type 枚举子集）"""
    return [k for k, perm in rule.items() if user is not None and user.has_permission(perm)]


def _filter_tools_for_user(user) -> list:
    """按用户权限过滤 TOOLS：无权限的工具不发给 LLM"""
    import copy
    out = []
    for tool in TOOLS:
        name = tool["function"]["name"]
        rule = TOOL_PERMS.get(name)
        if rule is None:
            out.append(tool)
            continue
        if isinstance(rule, dict):
            allowed = _allowed_subtypes(user, rule)
            if not allowed:
                continue
            t = copy.deepcopy(tool)
            props = t["function"]["parameters"]["properties"]
            for prop in props.values():
                if "enum" in prop and any(k in prop["enum"] for k in rule):
                    prop["enum"] = [k for k in prop["enum"] if k in allowed]
            out.append(t)
        elif user is not None and user.has_permission(rule):
            out.append(tool)
    return out


def _check_tool_perm(user, name: str, args: dict) -> bool:
    """执行前权限校验（双保险，防 LLM 绕过工具过滤）"""
    rule = TOOL_PERMS.get(name)
    if rule is None:
        return True
    if isinstance(rule, dict):
        key = args.get("entity_type") or args.get("order_type")
        perm = rule.get(key)
        return perm is None or (user is not None and user.has_permission(perm))
    return user is not None and user.has_permission(rule)


def _log_operation(db: Session, user, instruction: str, tool_name: str, args: dict, result: str):
    """写审计日志（写操作工具）"""
    import re as _re
    from app.models.system_config import OperationLog
    try:
        doc_no = ""
        m = _re.search(r"\b(?:PO|SO|RC|PAY|FG|IS|MO)-\S+", result or "")
        if m:
            doc_no = m.group(0)
        db.add(OperationLog(
            user_id=user.id if user else None,
            username=user.username if user else "AI",
            role_code=user.role_code if user else None,
            instruction=(instruction or "")[:1000],
            tool_name=tool_name,
            args_json=json.dumps(args, ensure_ascii=False, default=str)[:2000],
            result=(result or "")[:500],
            doc_no=doc_no,
            success=0 if (result or "").startswith(("❌", "⛔")) else 1,
        ))
        db.commit()
    except Exception:
        db.rollback()


TOOL_EXECUTORS = {k: globals()[f"_execute_{k}"] for k in
    ["query_entities", "create_order", "create_collection", "create_payment",
     "create_purchase_invoice", "create_sales_invoice",
     "issue_materials", "production_receipt",
     "query_inventory", "query_pending_approvals",
     "approve_order", "unapprove_order", "query_manual"]}


# ==================== AI 调用 ====================

def _call_llm(messages: list[dict], bot_config: BotConfig, api_key: str,
              tools: list | None = None, system_prompt: str | None = None) -> dict | None:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    base_url = (bot_config.base_url or "").rstrip("/") or (
        "https://api.deepseek.com" if bot_config.provider == "deepseek" else "https://api.openai.com"
    )
    payload = {
        "model": bot_config.model or "deepseek-chat",
        "messages": [{"role": "system", "content": system_prompt or (bot_config.system_prompt or SYSTEM_PROMPT)}] + messages,
        "temperature": bot_config.temperature or 0.1,
        "max_tokens": bot_config.max_tokens or 8192,
        "tools": tools if tools is not None else TOOLS,
        "tool_choice": "auto",
    }
    try:
        # 直连优先（trust_env=False 忽略环境代理，不依赖 VPN 开关）；
        # 直连被拒（网络隔离/需代理）时回退走环境代理重试一次
        try:
            with httpx.Client(timeout=120, trust_env=False) as client:
                resp = client.post(f"{base_url}/v1/chat/completions", headers=headers, json=payload)
        except (httpx.ConnectError, httpx.ProxyError, httpx.NetworkError):
            with httpx.Client(timeout=120, trust_env=True) as client:
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

def _capability_prompt(user, tools: list) -> str:
    """动态能力清单：注入当前用户身份与可用工具"""
    uname = user.display_name or user.username if user else "AI"
    role = user.role_name if user and user.role_name else "未分配角色"
    names = ", ".join(t["function"]["name"] for t in tools)
    return (
        "## 当前用户\n"
        f"- 用户：{uname}（角色：{role}）\n"
        f"- 可用工具：{names}\n"
        "只使用以上可用工具；用户没有权限的操作，明确告知「您没有该操作的权限」。"
    )


def process_message(message: str, history: list[dict], db: Session, user=None) -> dict:
    config = _get_config(db)
    if not config:
        return {"reply": "AI 未配置", "state": "error", "history": history or []}
    api_key = _get_api_key(config)
    if not api_key:
        return {"reply": "API Key 未配置或解密失败", "state": "error", "history": history or []}

    allowed_tools = _filter_tools_for_user(user)
    system_prompt = (config.system_prompt or SYSTEM_PROMPT) + "\n\n" + _capability_prompt(user, allowed_tools)

    messages = list(history or [])
    messages.append({"role": "user", "content": message})

    for _ in range(3):
        result = _call_llm(messages, config, api_key, tools=allowed_tools, system_prompt=system_prompt)
        if not result:
            return {"reply": "AI 调用失败，请稍后重试或检查 Agent设置", "state": "error", "history": history or []}

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

            # 逐个执行工具，追加 tool 结果（权限校验 + 审计日志）
            for tc in msg["tool_calls"]:
                fn = tc["function"]
                name = fn["name"]
                try:
                    args = json.loads(fn["arguments"])
                except:
                    args = {}

                if not _check_tool_perm(user, name, args):
                    tool_result = "⛔ 您没有执行该操作的权限，请向管理员申请相应菜单权限"
                else:
                    executor = TOOL_EXECUTORS.get(name)
                    tool_result = executor(args, db, user) if executor else f"未知工具：{name}"

                if name in AUDIT_TOOLS:
                    _log_operation(db, user, message, name, args, tool_result)

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
