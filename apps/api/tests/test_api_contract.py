from fastapi.testclient import TestClient

from app.main import app


def test_request_id_header_present():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")


def test_validation_error_unified_contract():
    # رقم سورة خارج النطاق يرفض قبل الوصول لقاعدة البيانات
    client = TestClient(app)
    response = client.get("/api/v1/ayahs/999/1")
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["meta"]["request_id"]
    assert body["meta"]["api_version"] == "v1"


def test_unknown_route_unified_contract():
    client = TestClient(app)
    response = client.get("/api/v1/no-such-route")
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["meta"]["request_id"]
