"""
MTS Bot 对话引擎 — Agent 模式（Function Calling）
=================================================
对话逻辑全由 LLM + Function Calling 处理，不再有状态机/关键词规则。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import User
from app.utils.auth import get_current_user
from app.utils.ai_chat import process_message

router = APIRouter(prefix="/chat", tags=["AI Bot"])

# ==================== 会话管理 ====================

class SessionStore:
    def __init__(self):
        self._sessions: dict[str, dict] = {}

    def get(self, sid: str) -> dict:
        return self._sessions.get(sid, {"history": []})

    def set(self, sid: str, state: dict):
        self._sessions[sid] = state

    def clear(self, sid: str):
        self._sessions.pop(sid, None)


sessions = SessionStore()


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

    sid = session_id or current_user.username
    session = sessions.get(sid)
    history = session.get("history", [])

    result = process_message(text, history, db, current_user)

    # 更新历史
    if result.get("history"):
        sessions.set(sid, {"history": result["history"]})

    return {
        "reply": result.get("reply", "好的"),
        "state": result.get("state", "idle"),
        "session_id": sid,
    }


@router.post("/reset")
def chat_reset(body: dict, current_user: User = Depends(get_current_user)):
    """重置会话"""
    sid = body.get("session_id", "") or current_user.username
    sessions.clear(sid)
    return {"message": "会话已重置"}
