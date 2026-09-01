"""系统配置密钥守卫测试：BotConfig.api_key / WecomConfig.secret 防双重加密

回归背景：读取接口把密文暴露给前端 → 表单回填 → 保存时被再次 encrypt() → 双重加密
导致 AI 助手 / 企微推送静默失效（解密兜底返回脱敏串 → LLM 401）。

修复：update 接口对 空值 / 脱敏串 / 原密文回传 → 跳过更新，保留原值；
仅对用户新输入的明文执行 encrypt()。
"""

import pytest

from app.database import SessionLocal
from app.models.system_config import BotConfig, WecomConfig
from app.utils.crypto import encrypt, decrypt, is_ciphertext

BASE = "/api/system"


# ==================== is_ciphertext 单元测试 ====================

class TestIsCiphertext:
    def test_real_cipher(self):
        assert is_ciphertext(encrypt("sk-test-key"))

    def test_masked_cipher(self):
        """脱敏串（gAAA****kDw= 形态）不应误判为密文"""
        c = encrypt("sk-test-key")
        masked = c[:4] + "****" + c[-4:]
        assert not is_ciphertext(masked)

    def test_plain_text(self):
        assert not is_ciphertext("sk-abcdef123456")

    def test_empty_and_none(self):
        assert not is_ciphertext("")
        assert not is_ciphertext(None)


# ==================== BotConfig.api_key 守卫 ====================

@pytest.fixture()
def bot_id(client, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.post(f"{BASE}/bot", json={
        "provider": "deepseek", "api_key": "sk-original-key-123456",
        "model": "deepseek-chat", "temperature": 0.1,
    }, headers=h)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _bot_cipher(db, bot_id):
    return db.query(BotConfig).filter(BotConfig.id == bot_id).first().api_key


def test_bot_update_masked_key_keeps_original(client, admin_token, bot_id):
    """旧 bug 路径：读取（密文脱敏）→ 表单回填 → 保存，key 必须保持不变"""
    db = SessionLocal()
    try:
        cipher = _bot_cipher(db, bot_id)
    finally:
        db.close()
    masked = cipher[:4] + "****" + cipher[-4:]  # 与 list_bot 脱敏逻辑一致

    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.put(f"{BASE}/bot/{bot_id}", json={"model": "gpt-4o", "api_key": masked}, headers=h)
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        assert _bot_cipher(db, bot_id) == cipher, "脱敏回传不应二次加密"
    finally:
        db.close()


def test_bot_update_cipher_roundtrip_keeps_original(client, admin_token, bot_id):
    """原密文原样回传（API 直调、无脱敏）也不应二次加密"""
    db = SessionLocal()
    try:
        cipher = _bot_cipher(db, bot_id)
    finally:
        db.close()

    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.put(f"{BASE}/bot/{bot_id}", json={"api_key": cipher}, headers=h)
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        assert _bot_cipher(db, bot_id) == cipher
    finally:
        db.close()


def test_bot_update_new_plain_key_updates(client, admin_token, bot_id):
    """用户输入新明文 → 正常加密更新，且可解密还原"""
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.put(f"{BASE}/bot/{bot_id}", json={"api_key": "sk-brand-new-key-999"}, headers=h)
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        cipher = _bot_cipher(db, bot_id)
    finally:
        db.close()
    assert cipher != "sk-brand-new-key-999"  # 已加密存储
    assert decrypt(cipher) == "sk-brand-new-key-999"


def test_bot_update_empty_key_keeps_original(client, admin_token, bot_id):
    """空字符串 → 跳过更新"""
    db = SessionLocal()
    try:
        cipher = _bot_cipher(db, bot_id)
    finally:
        db.close()

    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.put(f"{BASE}/bot/{bot_id}", json={"api_key": ""}, headers=h)
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        assert _bot_cipher(db, bot_id) == cipher
    finally:
        db.close()


def test_bot_update_without_key_field_keeps_original(client, admin_token, bot_id):
    """不传 api_key → 只改其他字段，key 不变"""
    db = SessionLocal()
    try:
        cipher = _bot_cipher(db, bot_id)
    finally:
        db.close()

    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.put(f"{BASE}/bot/{bot_id}", json={"temperature": 0.5}, headers=h)
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        assert _bot_cipher(db, bot_id) == cipher
    finally:
        db.close()


# ==================== WecomConfig.secret 守卫 ====================

@pytest.fixture()
def wecom_id(client, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.post(f"{BASE}/wecom", json={
        "corp_id": "ww-test", "agent_id": "1000002", "secret": "secret-original-123",
        "token": "tok", "encoding_aes_key": "aes",
    }, headers=h)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _wecom_cipher(db, wid):
    return db.query(WecomConfig).filter(WecomConfig.id == wid).first().secret


def test_wecom_update_masked_secret_keeps_original(client, admin_token, wecom_id):
    """旧 bug 路径：读取（密文）→ 回填 → 保存，secret 必须保持不变"""
    db = SessionLocal()
    try:
        cipher = _wecom_cipher(db, wecom_id)
    finally:
        db.close()
    masked = cipher[:4] + "****" + cipher[-4:]

    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.put(f"{BASE}/wecom/{wecom_id}", json={"agent_id": "1000003", "secret": masked}, headers=h)
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        assert _wecom_cipher(db, wecom_id) == cipher
    finally:
        db.close()


def test_wecom_update_new_secret_updates(client, admin_token, wecom_id):
    """新明文 → 正常加密更新"""
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.put(f"{BASE}/wecom/{wecom_id}", json={"secret": "brand-new-secret-777"}, headers=h)
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        assert decrypt(_wecom_cipher(db, wecom_id)) == "brand-new-secret-777"
    finally:
        db.close()
