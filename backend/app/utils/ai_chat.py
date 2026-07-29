"""AI API 调用封装 — 支持 DeepSeek / OpenAI 兼容接口"""

import json
import httpx
from sqlalchemy.orm import Session

from app.models.system_config import BotConfig
from app.utils.crypto import decrypt


def call_ai(
    system_prompt: str,
    messages: list[dict],
    bot_config: BotConfig,
) -> str | None:
    """调用 AI 模型，返回回复文本"""
    headers = {
        "Authorization": f"Bearer {bot_config.api_key}",
        "Content-Type": "application/json",
    }
    base_url = (bot_config.base_url or "").rstrip("/") or (
        "https://api.deepseek.com" if bot_config.provider == "deepseek"
        else "https://api.openai.com"
    )
    url = f"{base_url}/v1/chat/completions"
    payload = {
        "model": bot_config.model or "deepseek-chat",
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "temperature": bot_config.temperature or 0.1,
        "max_tokens": bot_config.max_tokens or 1024,
    }

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        import logging
        logging.getLogger("ai_chat").error(f"AI call failed: {e}")
        return None


AI_SYSTEM_PROMPT = """你是 MTS 系统的 AI 助手，帮助用户操作 ERP。

## 核心原则
- **不确定就问**，猜对了等用户确认再行动
- **用户否定就换**，不要固执
- **一次只问一个事**，不要一次问太多

## 意图判断规则
用户说「客户/买家/美国/出口」等 → sales_order（因为是销售员）
用户说「供应商/厂家/原材料/物料」 → purchase_order
用户说「产品/BOM」 → 倾向 sales_order，除非同时提到采购
用户说「生产/工单/做/制造」 → production_order
只说「下单」 → 反问：是销售订单、采购订单还是生产订单？

## 确认流程（loop）
你猜出意图后，必须问用户确认：
「您是想下销售订单，对吗？」
用户说「对/是/Y」 → 返回 create 类型
用户说「不是/不对/采购/销售」 → 换一个意图再问
用户说「算了/取消」 → 返回 chat 类型说好的

## 查询档案
用户说「查xxx/找xxx/xxx编码」 → 返回 query 类型
query 不需要确认

## 响应格式
必须返回 JSON。

### 确定可以下单
{"type":"create","intent":"purchase_order|sales_order|production_order","fields":{}}

### 查询档案
{"type":"query","entity":"supplier|customer|material|product","keyword":"搜索关键词"}

### 还没确定，继续聊天/反问
{"type":"chat","reply":"你的自然回复"}

## 字段收集
一旦用户确认了意图：
- purchase_order 需要：supplier, material, quantity, unit_price
- sales_order 需要：customer, product, quantity, unit_price
- production_order 需要：product, quantity, due_date
- 如果用户一句话说了多个字段，全部填到 fields 里
- 日期默认为今天"""


def get_active_bot_config(db: Session) -> BotConfig | None:
    """获取启用的 AI 配置，并解密 API Key"""
    config = db.query(BotConfig).filter(BotConfig.is_active == 1).first()
    if config and config.api_key:
        config.api_key = decrypt(config.api_key)
    return config


def process_with_ai(
    message: str,
    db: Session,
    history: list[dict] | None = None,
) -> dict | None:
    """用 AI 解析用户消息，传入最近对话历史让 LLM 理解上下文"""
    config = get_active_bot_config(db)
    if not config or not config.api_key:
        return None

    messages = [{"role": msg["role"], "content": msg["content"]}
                for msg in (history or [])]
    messages.append({"role": "user", "content": message})

    reply = call_ai(AI_SYSTEM_PROMPT, messages, config)
    if not reply:
        return None

    try:
        if "```json" in reply:
            reply = reply.split("```json")[1].split("```")[0].strip()
        elif "```" in reply:
            reply = reply.split("```")[1].split("```")[0].strip()
        result = json.loads(reply)
        return result
    except (json.JSONDecodeError, KeyError, IndexError):
        # AI 返回了非 JSON 文本 → 当 chat 类型处理
        return {"type": "chat", "reply": reply}
