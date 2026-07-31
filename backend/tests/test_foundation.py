"""基础档案 CRUD 测试（适配当前 API：materials 用 category、供应商/客户必填联系人等）"""


class TestMaterial:
    def test_create_material(self, client, auth_headers):
        resp = client.post("/api/foundation/materials", json={
            "name": "测试材料", "spec": "A1", "unit": "个",
            "category": "原材料", "purchase_price": 5,
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        return data["id"]

    def test_list_materials(self, client, auth_headers):
        resp = client.get("/api/foundation/materials", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_get_material(self, client, auth_headers):
        # 后端无单条 GET /materials/{id}，用列表+关键字查询
        resp = client.post("/api/foundation/materials", json={
            "name": "测试材料2", "spec": "B1", "unit": "kg",
            "category": "原材料", "purchase_price": 6,
        }, headers=auth_headers)
        mid = resp.json()["id"]
        resp = client.get("/api/foundation/materials?keyword=测试材料2", headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert any(i["id"] == mid for i in items)


class TestSupplier:
    def test_create_supplier(self, client, auth_headers):
        resp = client.post("/api/foundation/suppliers", json={
            "name": "测试供应商", "contact_person": "张三", "phone": "13800138000",
            "tax_id": "91330100TEST", "address": "杭州", "supplier_type": "供应商",
        }, headers=auth_headers)
        assert resp.status_code == 200
        return resp.json()["id"]

    def test_list_suppliers(self, client, auth_headers):
        resp = client.get("/api/foundation/suppliers", headers=auth_headers)
        assert resp.status_code == 200
        assert "items" in resp.json()


class TestCustomer:
    def test_create_customer(self, client, auth_headers):
        resp = client.post("/api/foundation/customers", json={
            "name_cn": "测试客户", "name_en": "Test Customer", "country": "美国",
            "contact_person": "李四", "phone": "13900139000",
            "tax_id": "91330000TEST", "address": "上海",
        }, headers=auth_headers)
        assert resp.status_code == 200
        return resp.json()["id"]


class TestProduct:
    def test_create_product(self, client, auth_headers):
        resp = client.post("/api/foundation/products", json={
            "name_cn": "测试产品", "spec": "X1", "unit": "件", "sale_price": 10,
        }, headers=auth_headers)
        assert resp.status_code == 200
        return resp.json()["id"]
