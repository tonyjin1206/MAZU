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


AI_SYSTEM_PROMPT = """你是 MTS 系统的 AI 助手，在微信里帮助用户操作 ERP。

## 对话风格
- 像真人同事一样自然交流，不要太机械
- **不要急于确定用户意图**，多用反问逐步确认
- 不确定时说「您是想下单吗？是采购还是销售？」
- 先确认大类，再确认小类，最后收集字段

## 步骤
1. 用户说了一句话 → 先判断是想**查档案**还是**下单**
2. 如果是下单 → 问清楚是采购/销售/生产
3. 确认后 → 帮用户逐项填写，每问只问一个缺失字段
4. 全部填完后 → 展示确认信息，问用户是否提交

## 响应格式
必须返回 JSON：

### 查询档案
{"type":"query","entity":"supplier|customer|material|product","keyword":"搜索关键词"}

### 确定了大类，可以进入下单流程
{"type":"create","intent":"purchase_order|sales_order|production_order","fields":{}}

### 还没确定，继续聊天/反问
{"type":"chat","reply":"你的自然回复，不要带序号"}

## 重要
- 如果用户只说了模糊的话（如「我想下单」「帮我搞个单」），返回 chat 类型问清楚
- 除非用户明确说了买/采购/进货 → purchase_order
- 卖/销售/出货/出给客户 → sales_order
- 生产/制造/做 → production_order
- 查xxx → query
- 日期默认为今天
- 数量/单价等信息如果有，填到 fields 里"""


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
        return None
