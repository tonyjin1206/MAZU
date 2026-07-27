"""基础档案 CRUD 测试"""


class TestMaterial:
    def test_create_material(self, client, auth_headers):
        resp = client.post("/api/foundation/materials", json={
            "code": "MAT-001",
            "name": "测试材料",
            "spec": "A1",
            "unit": "个",
            "material_type": "原材料",
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
        # 先创建
        resp = client.post("/api/foundation/materials", json={
            "code": "MAT-002", "name": "测试材料2", "spec": "B1",
            "unit": "kg", "material_type": "原材料",
        }, headers=auth_headers)
        mid = resp.json()["id"]
        # 查询
        resp = client.get(f"/api/foundation/materials/{mid}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "测试材料2"


class TestSupplier:
    def test_create_supplier(self, client, auth_headers):
        resp = client.post("/api/foundation/suppliers", json={
            "code": "SUP-001", "name": "测试供应商",
            "contact_person": "张三", "phone": "13800138000",
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
            "code": "CUS-001", "name_cn": "测试客户",
            "name_en": "Test Customer", "country": "美国",
        }, headers=auth_headers)
        assert resp.status_code == 200
        return resp.json()["id"]


class TestProduct:
    def test_create_product(self, client, auth_headers):
        resp = client.post("/api/foundation/products", json={
            "code": "PROD-001", "name": "测试产品",
            "spec": "X1", "unit": "件",
            "product_type": "成品",
        }, headers=auth_headers)
        assert resp.status_code == 200
        return resp.json()["id"]
