"""SM HR 领域测试：部门、员工、请假、考勤、薪酬与统计。"""

import pytest
from fastapi.testclient import TestClient

from app import base
from app.main import VERSION, app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(base, "internal_api_key", lambda: "TEST")
    base.reset_state()
    from app.main import _init as init_db
    init_db()
    with TestClient(app) as c:
        c.headers["X-Internal-Token"] = "TEST"
        yield c


def _dept(client, name="研发部"):
    return client.post("/api/hr/departments", json={"name": name, "manager": "刘总"}).json()["id"]


def _emp(client, no="E001", name="张三"):
    return client.post("/api/hr/employees", json={"employee_no": no, "name": name, "department": "研发部", "position": "工程师", "email": f"{no}@corp.cn"}).json()["id"]


def test_health_and_version(client):
    r = client.get("/health", headers={"X-Request-Id": "suite-test"})
    assert r.status_code == 200
    assert r.json()["version"] == VERSION


def test_department_and_employee(client):
    _dept(client)
    _emp(client)
    assert client.post("/api/hr/departments", json={"name": "研发部"}).status_code == 409
    assert client.post("/api/hr/employees", json={"employee_no": "E001", "name": "李四", "department": "研发部", "position": "xx", "email": "e2@corp.cn"}).status_code == 409
    assert client.get("/api/hr/departments").json()["total"] == 1
    assert client.get("/api/hr/employees").json()["total"] == 1


def test_employee_requires_dept(client):
    assert client.post("/api/hr/employees", json={"employee_no": "E099", "name": "王五", "department": "幽灵部", "position": "xx", "email": "e9@corp.cn"}).status_code == 404


def test_leave_flow(client):
    _dept(client)
    emp_id = _emp(client)
    leave = client.post("/api/hr/leave", json={"employee_id": emp_id, "leave_type": "年假", "start_date": "2026-09-01", "end_date": "2026-09-03"})
    assert leave.status_code == 201
    assert leave.json()["days"] == 3
    leave_id = leave.json()["id"]
    assert client.post(f"/api/hr/leave/{leave_id}/approve").json()["status"] == "approved"
    assert client.post(f"/api/hr/leave/{leave_id}/reject").status_code == 404
    assert client.get("/api/hr/leave").json()["total"] == 1


def test_attendance(client):
    _dept(client)
    emp_id = _emp(client)
    assert client.post("/api/hr/attendance", json={"employee_id": emp_id, "day": "2026-08-31", "status": "present"}).json()["status"] == "present"
    assert client.post("/api/hr/attendance", json={"employee_id": "no-such-id", "day": "2026-08-31", "status": "absent"}).status_code == 404


def test_payroll(client):
    _dept(client)
    emp_id = _emp(client)
    pay = client.post("/api/hr/payroll", json={"employee_id": emp_id, "period": "2026-08", "base_salary": 10000, "bonus": 2000, "deductions": 1500}).json()
    assert pay["net_pay"] == 10500


def test_stats(client):
    _dept(client)
    _emp(client)
    stats = client.get("/api/hr/stats").json()
    assert stats["employees"] == 1
    assert stats["active"] == 1
    assert stats["by_department"][0]["count"] == 1


def test_manifest_and_crypto(client):
    assert client.get("/api/integration/manifest").json()["version"] == VERSION
    enc = client.post("/api/crypto/encrypt", json={"value": "x"}).json()["ciphertext"]
    assert client.post("/api/crypto/decrypt", json={"value": enc}).json()["plaintext"] == "x"


def test_write_requires_auth(client):
    del client.headers["X-Internal-Token"]
    assert client.post("/api/hr/departments", json={"name": "d"}).status_code == 401
