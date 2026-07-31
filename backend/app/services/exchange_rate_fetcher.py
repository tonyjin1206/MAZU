"""汇率获取 — 国内数据源（腾讯财经 qt.gtimg.cn，无 key，实时）

返回格式（GBK 编码，逗号分隔多币种）：
  v_whUSDCNY="310~美元人民币~USDCNY~6.7526~0~20260731233702~..."
  字段索引: [3]=现价  [5]=时间戳(YYYYMMDDHHMMSS)

用法:
  from app.services.exchange_rate_fetcher import fetch_rates
  rates = fetch_rates(["USD", "EUR"])   # -> {"USD": 6.7526, "EUR": 7.7704}（兑 CNY）
"""

import logging

import httpx

logger = logging.getLogger(__name__)

TENCENT_URL = "https://qt.gtimg.cn/q="


def fetch_rates(codes: list[str], timeout: float = 10.0) -> dict[str, float]:
    """批量查询币种兑 CNY 汇率（国内源腾讯财经）

    Args:
        codes: ISO 币种代码列表（如 ["USD", "EUR"]）
    Returns:
        {code: rate}，查询失败的币种不包含在结果中
    """
    codes = [c for c in codes if c and c != "CNY"]
    if not codes:
        return {}
    symbols = ",".join(f"wh{c}CNY" for c in codes)
    try:
        resp = httpx.get(TENCENT_URL + symbols, timeout=timeout)
        resp.raise_for_status()
        text = resp.content.decode("gbk", errors="ignore")
    except Exception as e:
        logger.error(f"腾讯汇率获取失败: {e}")
        return {}

    rates: dict[str, float] = {}
    for line in text.split(";"):
        line = line.strip()
        if not line.startswith("v_wh") or '="' not in line:
            continue
        try:
            inner = line.split('="', 1)[1].rstrip('";')
            parts = inner.split("~")
            pair = parts[2]  # 如 USDCNY
            if not pair.endswith("CNY"):
                continue
            code = pair[:-3]
            price = float(parts[3])
            if price > 0:
                rates[code] = price
        except (ValueError, IndexError):
            continue
    return rates


def convert_to_base(rates_cny: dict[str, float], base_code: str) -> dict[str, float]:
    """把「兑 CNY」汇率换算为「兑本位币」汇率

    Args:
        rates_cny: {code: 兑CNY汇率}
        base_code: 本位币代码（如 CNY/USD）
    Returns:
        {code: 兑本位币汇率}；base 不在表中时返回原表（无法换算）
    """
    if base_code == "CNY" or base_code not in rates_cny:
        return rates_cny
    base_rate = rates_cny[base_code]
    return {c: round(r / base_rate, 6) for c, r in rates_cny.items() if c != base_code}
