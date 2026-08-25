"""退税模块 API 路由（生产企业免抵退）"""

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.auth import User
from app.models.foundation import HsCode, Product, Supplier
from app.models.sales import CustomsDeclaration, SalesOrder
from app.models.tax_refund import (
    TaxRefundInputInvoice, TaxRefundDeclaration,
    TaxRefundDetail, TaxRefundProgress,
    TaxRefundDeclarationRow,
)
from app.models.purchase import PurchaseInvoice
from app.schemas.tax_refund import (
    TaxRefundInputInvoiceCreate, TaxRefundInputInvoiceOut,
    TaxRefundDeclarationCreate, TaxRefundDeclarationOut,
    TaxRefundDeclarationRowCreate, TaxRefundDeclarationRowOut,
    TaxRefundDetailCreate, TaxRefundDetailOut,
    TaxRefundCalculationRequest, TaxRefundCalculationResult,
    TaxRefundProgressCreate,
)
from app.utils.auth import get_current_user

router = APIRouter()


# ==================== 免抵退计算 ====================

def calculate_exempt_credit_refund(
    export_amount_fob: float = 0,
    refund_rate: float = 0,
    tax_rate: float = 13,
    domestic_tax: float = 0,
    input_tax: float = 0,
    last_period_deduction: float = 0,
):
    """生产企业免抵退税额计算"""
    non_deductible = export_amount_fob * (tax_rate - refund_rate) / 100
    current_tax_due = domestic_tax - (input_tax - non_deductible) - last_period_deduction
    refundable = export_amount_fob * refund_rate / 100
    deduction = max(0, -current_tax_due)
    if deduction > 0:
        actual_refund = min(deduction, refundable)
        exemption = refundable - actual_refund
    else:
        actual_refund = 0
        exemption = refundable
    return {
        "non_deductible_amount": round(non_deductible, 2),
        "taxable_amount": round(current_tax_due, 2),
        "current_deduction": round(deduction, 2),
        "refundable_amount": round(refundable, 2),
        "actual_refund": round(actual_refund, 2),
        "exemption_amount": round(exemption, 2),
    }


@router.post("/calculate", response_model=TaxRefundCalculationResult, tags=["退税管理"])
def calculate_tax_refund(
    data: TaxRefundCalculationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """免抵退税额计算"""
    result = calculate_exempt_credit_refund(
        export_amount_fob=data.export_amount_fob,
        refund_rate=data.refund_rate,
        tax_rate=data.tax_rate,
        domestic_tax=data.domestic_tax,
        input_tax=data.input_tax,
        last_period_deduction=data.last_period_deduction,
    )
    return TaxRefundCalculationResult(**result)


# ==================== 进项发票管理 ====================

@router.get("/input-invoices", tags=["退税管理"])
def list_input_invoices(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    certification_status: str = Query(""),
    refund_match_status: str = Query(""),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """进项发票列表"""
    query = db.query(TaxRefundInputInvoice)
    if certification_status:
        query = query.filter(TaxRefundInputInvoice.certification_status == certification_status)
    if refund_match_status:
        query = query.filter(TaxRefundInputInvoice.refund_match_status == refund_match_status)
    total = query.count()
    items = query.order_by(TaxRefundInputInvoice.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [
        {"id": inv.id, "invoice_no": inv.invoice_no,
         "supplier_id": inv.supplier_id,
         "supplier_name": inv.supplier.name if inv.supplier else "",
         "supplier_tax_id": inv.supplier.tax_id if inv.supplier else "",
         "amount": inv.amount, "tax_amount": inv.tax_amount,
         "total_amount": inv.total_amount,
         "invoice_date": str(inv.invoice_date),
         "certification_status": inv.certification_status,
         "refund_match_status": inv.refund_match_status,
        } for inv in items
    ]}


@router.post("/input-invoices", tags=["退税管理"])
def create_input_invoice(
    data: TaxRefundInputInvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建进项发票记录"""
    inv = TaxRefundInputInvoice(**data.model_dump())
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return {"id": inv.id, "invoice_no": inv.invoice_no, "message": "进项发票已登记"}


# ==================== 退税申报 ====================

@router.post("/declarations", tags=["退税管理"])
def create_declaration(
    data: TaxRefundDeclarationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建退税申报表"""
    calc = calculate_exempt_credit_refund(
        export_amount_fob=data.export_amount_fob,
        refund_rate=data.refund_rate,
        tax_rate=data.tax_rate,
        domestic_tax=data.domestic_tax,
        input_tax=data.input_tax,
        last_period_deduction=data.last_period_deduction,
    )
    declaration = TaxRefundDeclaration(
        declaration_no=data.declaration_no,
        declare_date=data.declare_date,
        period=data.period,
        batch=data.batch or 1,
        export_amount_fob=data.export_amount_fob,
        tax_rate=data.tax_rate,
        refund_rate=data.refund_rate,
        non_deductible_amount=calc["non_deductible_amount"],
        domestic_tax=data.domestic_tax,
        input_tax=data.input_tax,
        last_period_deduction=data.last_period_deduction,
        current_tax_due=calc["taxable_amount"],
        current_deduction=calc["current_deduction"],
        refundable_amount=calc["refundable_amount"],
        actual_refund=calc["actual_refund"],
        exemption_amount=calc["exemption_amount"],
        customs_ids=data.customs_ids,
        input_invoice_ids=data.input_invoice_ids,
        remark=data.remark,
        created_by=current_user.display_name or current_user.username,
    )
    db.add(declaration)
    db.commit()
    db.refresh(declaration)
    return {"id": declaration.id, "declaration_no": declaration.declaration_no, "message": "申报已创建"}


@router.get("/declarations", tags=["退税管理"])
def list_declarations(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    status: str = Query(""),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """退税申报列表"""
    query = db.query(TaxRefundDeclaration)
    if status:
        query = query.filter(TaxRefundDeclaration.status == status)
    total = query.count()
    items = query.order_by(TaxRefundDeclaration.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [
        {
            "id": d.id, "declaration_no": d.declaration_no,
            "period": d.period, "batch": d.batch or 1,
            "declare_date": str(d.declare_date),
            "export_amount_fob": d.export_amount_fob,
            "refundable_amount": round(sum(
                (r.refundable_amount or 0) for r in db.query(TaxRefundDeclarationRow).filter(
                    TaxRefundDeclarationRow.declaration_id == d.id).all()
            ), 2),
            "actual_refund_amount": d.actual_refund_amount or 0,
            "actual_refund": d.actual_refund,
            "exemption_amount": d.exemption_amount,
            "status": d.status,
            "created_at": str(d.created_at) if d.created_at else "",
        } for d in items
    ]}


@router.get("/declarations/{decl_id}", tags=["退税管理"])
def get_declaration(decl_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """申报详情（含明细行）"""
    d = db.query(TaxRefundDeclaration).filter(TaxRefundDeclaration.id == decl_id).first()
    if not d:
        raise HTTPException(404, "申报不存在")
    rows = db.query(TaxRefundDeclarationRow).filter(
        TaxRefundDeclarationRow.declaration_id == decl_id).all()
    row_list = []
    for r in rows:
        inv = db.query(TaxRefundInputInvoice).filter(TaxRefundInputInvoice.id == r.input_invoice_id).first() if r.input_invoice_id else None
        row_list.append({
            "id": r.id, "seq": r.seq or "", "assoc_no": r.assoc_no or "",
            "tax_type": r.tax_type or "V", "voucher_type": r.voucher_type or "",
            "voucher_no": r.voucher_no or "", "supplier_tax_id": r.supplier_tax_id or "",
            "invoice_date": str(r.invoice_date) if r.invoice_date else "",
            "product_code": r.product_code or "", "product_name": r.product_name or "",
            "unit": r.unit or "", "quantity": r.quantity or 0,
            "taxable_amount": r.taxable_amount or 0,
            "tax_rate": r.tax_rate or 13, "refund_rate": r.refund_rate or 13,
            "refundable_amount": r.refundable_amount or 0,
            "input_invoice_id": r.input_invoice_id,
            "invoice_no": inv.invoice_no if inv else "",
            "supplier_name": inv.supplier.name if inv and inv.supplier else "",
        })
    return {
        "id": d.id, "declaration_no": d.declaration_no,
        "period": d.period, "declare_date": str(d.declare_date),
        "batch": d.batch or 1,
        "status": d.status, "remark": d.remark or "",
        "actual_refund_amount": d.actual_refund_amount or 0,
        "created_at": str(d.created_at) if d.created_at else "",
        "rows": row_list,
    }


@router.put("/declarations/{decl_id}/submit", tags=["退税管理"])
def submit_declaration(decl_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """申报退税（提交后不可修改）"""
    d = db.query(TaxRefundDeclaration).filter(TaxRefundDeclaration.id == decl_id).first()
    if not d:
        raise HTTPException(404, "申报不存在")
    if d.status != "待申报":
        raise HTTPException(400, "只有待申报状态可以提交")
    d.status = "已申报"
    db.commit()
    return {"message": "申报已提交"}


@router.put("/declarations/{decl_id}/cancel-submit", tags=["退税管理"])
def cancel_submit(decl_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """取消申报"""
    d = db.query(TaxRefundDeclaration).filter(TaxRefundDeclaration.id == decl_id).first()
    if not d:
        raise HTTPException(404, "申报不存在")
    if d.status != "已申报":
        raise HTTPException(400, "只有已申报状态可以取消申报")
    d.status = "待申报"
    db.commit()
    return {"message": "申报已取消"}


@router.put("/declarations/{decl_id}/refund", tags=["退税管理"])
def process_refund(decl_id: int, data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """完成退税"""
    d = db.query(TaxRefundDeclaration).filter(TaxRefundDeclaration.id == decl_id).first()
    if not d:
        raise HTTPException(404, "申报不存在")
    if d.status != "已申报":
        raise HTTPException(400, "只有已申报状态可以退税")
    try:
        amount = float(data.get("amount", 0) or 0)
    except (TypeError, ValueError):
        raise HTTPException(400, "退税金额必须为数字")
    if amount <= 0:
        raise HTTPException(400, "退税金额必须大于 0")
    if amount > (d.actual_refund or 0):
        raise HTTPException(400, f"退税金额不能超过应退税额 ¥{d.actual_refund or 0:,.2f}")
    d.status = "已退税"
    d.actual_refund_amount = amount
    db.commit()
    return {"message": "退税完成"}


@router.put("/declarations/{decl_id}/cancel-refund", tags=["退税管理"])
def cancel_refund(decl_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """取消退税"""
    d = db.query(TaxRefundDeclaration).filter(TaxRefundDeclaration.id == decl_id).first()
    if not d:
        raise HTTPException(404, "申报不存在")
    if d.status != "已退税":
        raise HTTPException(400, "只有已退税状态可以取消退税")
    d.status = "已申报"
    d.actual_refund_amount = 0
    db.commit()
    return {"message": "退税已取消"}


@router.delete("/declarations/{decl_id}", tags=["退税管理"])
def delete_declaration(decl_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """删除退税申报（仅待申报可删；已申报/已退税须先走取消流程）"""
    d = db.query(TaxRefundDeclaration).filter(TaxRefundDeclaration.id == decl_id).first()
    if not d:
        raise HTTPException(404, "申报不存在")
    if d.status != "待申报":
        raise HTTPException(400, f"仅待申报状态可删除（当前 {d.status}），请先取消申报/取消退税")
    # 回滚关联进项发票状态
    rows = db.query(TaxRefundDeclarationRow).filter(TaxRefundDeclarationRow.declaration_id == decl_id).all()
    for row in rows:
        if row.input_invoice_id:
            inv = db.query(TaxRefundInputInvoice).filter(TaxRefundInputInvoice.id == row.input_invoice_id).first()
            if inv:
                inv.refund_match_status = "未匹配"
                if inv.purchase_invoice_id:
                    pi = db.query(PurchaseInvoice).filter(PurchaseInvoice.id == inv.purchase_invoice_id).first()
                    if pi:
                        pi.status = "未匹配"
        db.delete(row)
    db.delete(d)
    db.commit()
    return {"message": "申报已删除"}


# ==================== 申报明细行（标准格式） ====================

@router.post("/declarations/{decl_id}/rows", tags=["退税管理"])
def create_declaration_row(decl_id: int, data: TaxRefundDeclarationRowCreate,
                           db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """添加申报明细行"""
    decl = db.query(TaxRefundDeclaration).filter(TaxRefundDeclaration.id == decl_id).first()
    if not decl:
        raise HTTPException(404, "申报不存在")
    inv = db.query(TaxRefundInputInvoice).filter(TaxRefundInputInvoice.id == data.input_invoice_id).first()
    existing = db.query(TaxRefundDeclarationRow).filter(
        TaxRefundDeclarationRow.declaration_id == decl_id).count()
    seq = f"{existing + 1:08d}"
    batch_str = f"{decl.batch or 1:03d}"
    assoc_no = f"{decl.period}{batch_str}{existing + 1}"
    refundable = round((data.taxable_amount or 0) * (data.refund_rate or 0) / 100, 2)
    row = TaxRefundDeclarationRow(
        declaration_id=decl_id, seq=seq, assoc_no=assoc_no,
        voucher_type=data.voucher_type or "增值税专用发票",
        voucher_no=inv.invoice_no if inv else data.voucher_no,
        supplier_tax_id=inv.supplier.tax_id if inv and inv.supplier else "",
        invoice_date=inv.invoice_date if inv else None,
        product_code=data.product_code, product_name=data.product_name,
        unit=data.unit, quantity=data.quantity, taxable_amount=data.taxable_amount or 0,
        tax_rate=data.tax_rate or 13, refund_rate=data.refund_rate or 13,
        refundable_amount=refundable, input_invoice_id=data.input_invoice_id,
    )
    db.add(row)
    if inv:
        inv.refund_match_status = "已匹配"
        # 同步更新采购发票状态
        if inv.purchase_invoice_id:
            pi = db.query(PurchaseInvoice).filter(PurchaseInvoice.id == inv.purchase_invoice_id).first()
            if pi:
                pi.status = "已匹配(退税)"
    db.commit()
    db.refresh(row)
    return {"id": row.id, "assoc_no": assoc_no, "seq": seq, "message": "明细行已添加"}


@router.delete("/declarations/{decl_id}/rows/{row_id}", tags=["退税管理"])
def delete_declaration_row(decl_id: int, row_id: int,
                           db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """删除申报明细行"""
    row = db.query(TaxRefundDeclarationRow).filter(
        TaxRefundDeclarationRow.id == row_id).first()
    if not row:
        raise HTTPException(404, "明细行不存在")
    # 回滚进项发票匹配状态
    if row.input_invoice_id:
        remaining = db.query(TaxRefundDeclarationRow).filter(
            TaxRefundDeclarationRow.input_invoice_id == row.input_invoice_id,
            TaxRefundDeclarationRow.id != row_id,
        ).count()
        if remaining == 0:
            inv = db.query(TaxRefundInputInvoice).filter(TaxRefundInputInvoice.id == row.input_invoice_id).first()
            if inv:
                inv.refund_match_status = "未匹配"
                if inv.purchase_invoice_id:
                    pi = db.query(PurchaseInvoice).filter(PurchaseInvoice.id == inv.purchase_invoice_id).first()
                    if pi:
                        pi.status = "未匹配"
        db.delete(row)
    remaining = db.query(TaxRefundDeclarationRow).filter(
        TaxRefundDeclarationRow.declaration_id == decl_id).order_by(TaxRefundDeclarationRow.id).all()
    decl = db.query(TaxRefundDeclaration).filter(TaxRefundDeclaration.id == decl_id).first()
    batch_str = f"{decl.batch or 1:03d}" if decl else "001"
    for i, r in enumerate(remaining):
        r.seq = f"{i+1:08d}"
        r.assoc_no = f"{decl.period}{batch_str}{i+1}" if decl else r.assoc_no
    db.commit()
    return {"message": "明细行已删除"}


@router.put("/declarations/{decl_id}/rows/{row_id}", tags=["退税管理"])
def update_declaration_row(decl_id: int, row_id: int, data: dict, db: Session = Depends(get_db),
                           current_user: User = Depends(get_current_user)):
    """更新申报明细行"""
    row = db.query(TaxRefundDeclarationRow).filter(
        TaxRefundDeclarationRow.id == row_id, TaxRefundDeclarationRow.declaration_id == decl_id).first()
    if not row:
        raise HTTPException(404, "明细行不存在")
    for field in ["product_code", "product_name", "unit", "quantity", "taxable_amount", "tax_rate", "refund_rate"]:
        if field in data:
            if field in ("quantity", "taxable_amount", "tax_rate", "refund_rate"):
                try:
                    setattr(row, field, float(data[field]))
                except (TypeError, ValueError):
                    raise HTTPException(400, f"{field} 必须为数字")
            else:
                setattr(row, field, data[field])
    row.refundable_amount = round((row.taxable_amount or 0) * (row.refund_rate or 0) / 100, 2)
    db.commit()
    return {"message": "明细行已更新"}


@router.get("/declarations/{decl_id}/rows", tags=["退税管理"])
def list_declaration_rows(decl_id: int, db: Session = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    """获取申报明细行列表"""
    rows = db.query(TaxRefundDeclarationRow).filter(
        TaxRefundDeclarationRow.declaration_id == decl_id).order_by(TaxRefundDeclarationRow.id).all()
    result = []
    for r in rows:
        inv = db.query(TaxRefundInputInvoice).filter(TaxRefundInputInvoice.id == r.input_invoice_id).first() if r.input_invoice_id else None
        result.append({
            "id": r.id, "seq": r.seq or "", "assoc_no": r.assoc_no or "",
            "tax_type": r.tax_type or "V", "voucher_type": r.voucher_type or "",
            "voucher_no": r.voucher_no or "", "supplier_tax_id": r.supplier_tax_id or "",
            "invoice_date": str(r.invoice_date) if r.invoice_date else "",
            "product_code": r.product_code or "", "product_name": r.product_name or "",
            "unit": r.unit or "", "quantity": r.quantity or 0,
            "taxable_amount": r.taxable_amount or 0,
            "tax_rate": r.tax_rate or 13, "refund_rate": r.refund_rate or 13,
            "refundable_amount": r.refundable_amount or 0,
            "input_invoice_id": r.input_invoice_id,
            "invoice_no": inv.invoice_no if inv else "",
            "supplier_name": inv.supplier.name if inv and inv.supplier else "",
        })
    return {"items": result}


# ==================== 退税明细（旧格式，兼容） ====================

@router.post("/declaration-details", tags=["退税管理"])
def create_declaration_detail(data: TaxRefundDetailCreate, db: Session = Depends(get_db),
                              current_user: User = Depends(get_current_user)):
    hs_code = db.query(HsCode).filter(HsCode.id == data.hs_code_id).first()
    refund_rate = data.refund_rate or (hs_code.refund_rate if hs_code else 0)
    refundable = data.export_amount_fob * refund_rate / 100
    detail = TaxRefundDetail(
        declaration_id=data.declaration_id, customs_id=data.customs_id,
        order_id=data.order_id, hs_code_id=data.hs_code_id, product_id=data.product_id,
        export_quantity=data.export_quantity, export_amount_fob=data.export_amount_fob,
        refund_rate=refund_rate, refundable_amount=refundable,
        input_invoice_ids=data.input_invoice_ids, remark=data.remark,
    )
    db.add(detail)
    db.commit()
    db.refresh(detail)
    return {"id": detail.id, "message": "申报明细已添加"}


# ==================== 退税进度 ====================

@router.post("/progress", tags=["退税管理"])
def create_progress(data: TaxRefundProgressCreate, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    from app.models.tax_refund import TaxRefundProgress
    progress = TaxRefundProgress(**data.model_dump())
    db.add(progress)
    db.commit()
    db.refresh(progress)
    return {"id": progress.id, "message": "进度已记录"}


@router.get("/progress", tags=["退税管理"])
def list_progress(declaration_id: int, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    from app.models.tax_refund import TaxRefundProgress
    items = db.query(TaxRefundProgress).filter(
        TaxRefundProgress.declaration_id == declaration_id
    ).order_by(TaxRefundProgress.action_date).all()
    return {"items": [
        {"id": p.id, "action": p.action, "action_date": str(p.action_date),
         "operator": p.operator, "result": p.result, "remark": p.remark,
        } for p in items
    ]}


# ==================== 报关单退税状态关联 ====================

@router.get("/customs-for-refund", tags=["退税管理"])
def list_customs_for_refund(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                            db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """待退税报关单"""
    items = db.query(CustomsDeclaration).filter(
        CustomsDeclaration.status.in_(["已放行", "已结关"])
    ).order_by(CustomsDeclaration.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    total = db.query(CustomsDeclaration).filter(
        CustomsDeclaration.status.in_(["已放行", "已结关"])).count()
    return {"total": total, "page": page, "page_size": page_size, "items": [
        {"id": c.id, "customs_no": c.customs_no, "product_name": c.product_name,
         "customs_amount": c.declare_amount,
         "declare_date": str(c.declare_date),
         "hs_code": c.hs_code.hs_code if c.hs_code else "",
         "refund_rate": c.hs_code.refund_rate if c.hs_code else 0,
        } for c in items
    ]}


# ==================== 退税统计 ====================

@router.get("/statistics", tags=["退税管理"])
def get_refund_statistics(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """退税统计"""
    from sqlalchemy import func
    total_declarations = db.query(TaxRefundDeclaration).count()
    total_refund = db.query(func.coalesce(func.sum(TaxRefundDeclaration.actual_refund), 0)).scalar()
    pending = db.query(TaxRefundDeclaration).filter(TaxRefundDeclaration.status == "待申报").count()
    return {
        "total_declarations": total_declarations,
        "total_refund_amount": round(float(total_refund), 2),
        "pending_declarations": pending,
    }
