"""HR 业务深化测试：员工档案、考勤、入转调离、请假。"""
from __future__ import annotations

H = {"X-Internal-Token": "test-internal-key-12345"}


async def _make_profile(client, emp_no="E-001", name="张三", dept="研发部"):
    return await client.post("/api/hr/profiles", json={
        "emp_no": emp_no, "name": name, "department": dept,
        "position": "工程师", "phone": "13800000000", "hire_date": "2024-01-01",
    }, headers=H)


# ═══════════════════════════════════════════════════════════
# 员工档案
# ═══════════════════════════════════════════════════════════
class TestProfile:
    async def test_create_profile(self, client):
        resp = await _make_profile(client, "E-100", "王五")
        assert resp.status_code == 201
        assert resp.json()["status"] == "probation"

    async def test_create_requires_token(self, client):
        resp = await client.post("/api/hr/profiles", json={
            "emp_no": "E-NOAUTH", "name": "x", "hire_date": "2024-01-01",
        })
        assert resp.status_code in (401, 403)

    async def test_duplicate_emp_no(self, client):
        await _make_profile(client, "E-DUP")
        resp = await _make_profile(client, "E-DUP")
        assert resp.status_code == 409

    async def test_future_hire_date_rejected(self, client):
        resp = await client.post("/api/hr/profiles", json={
            "emp_no": "E-FUT", "name": "未来", "hire_date": "2099-01-01",
        }, headers=H)
        assert resp.status_code == 400

    async def test_promote_probation_to_regular(self, client):
        p = (await _make_profile(client, "E-REG")).json()
        resp = await client.patch(f"/api/hr/profiles/{p['id']}/status",
                                  json={"status": "regular"}, headers=H)
        assert resp.status_code == 200
        assert resp.json()["status"] == "regular"

    async def test_invalid_status_transition(self, client):
        p = (await _make_profile(client, "E-INV")).json()
        # left 后不可再转 regular
        await client.patch(f"/api/hr/profiles/{p['id']}/status",
                           json={"status": "left"}, headers=H)
        resp = await client.patch(f"/api/hr/profiles/{p['id']}/status",
                                  json={"status": "regular"}, headers=H)
        assert resp.status_code == 409

    async def test_list_profiles_filter_keyword(self, client):
        await _make_profile(client, "E-KW", "关键词员工")
        resp = await client.get("/api/hr/profiles?status=probation&keyword=关键词", headers=H)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_get_profile_not_found(self, client):
        resp = await client.get("/api/hr/profiles/nope", headers=H)
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════
# 考勤
# ═══════════════════════════════════════════════════════════
class TestAttendance:
    async def test_create_attendance(self, client):
        p = (await _make_profile(client, "E-ATT")).json()
        resp = await client.post("/api/hr/attendance", json={
            "employee_id": p["id"], "att_date": "2026-09-16", "status": "present",
        }, headers=H)
        assert resp.status_code == 201

    async def test_duplicate_attendance_same_day(self, client):
        p = (await _make_profile(client, "E-ATT2")).json()
        body = {"employee_id": p["id"], "att_date": "2026-09-15"}
        await client.post("/api/hr/attendance", json=body, headers=H)
        resp = await client.post("/api/hr/attendance", json=body, headers=H)
        assert resp.status_code == 409

    async def test_check_in_after_check_out_rejected(self, client):
        p = (await _make_profile(client, "E-ATT3")).json()
        resp = await client.post("/api/hr/attendance", json={
            "employee_id": p["id"], "att_date": "2026-09-14",
            "check_in": "2026-09-14T18:00:00", "check_out": "2026-09-14T09:00:00",
        }, headers=H)
        assert resp.status_code == 400

    async def test_attendance_list_filter(self, client):
        p = (await _make_profile(client, "E-ATT4")).json()
        await client.post("/api/hr/attendance", json={
            "employee_id": p["id"], "att_date": "2026-09-13", "status": "late",
        }, headers=H)
        resp = await client.get(f"/api/hr/attendance?employee_id={p['id']}&status=late", headers=H)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1


# ═══════════════════════════════════════════════════════════
# 入转调离
# ═══════════════════════════════════════════════════════════
class TestChange:
    async def test_create_change(self, client):
        p = (await _make_profile(client, "E-CHG")).json()
        resp = await client.post("/api/hr/changes", json={
            "employee_id": p["id"], "change_type": "transfer",
            "from_department": "研发部", "to_department": "产品部",
            "effective_date": "2026-09-20", "reason": "组织调整",
        }, headers=H)
        assert resp.status_code == 201
        assert resp.json()["status"] == "draft"

    async def test_past_effective_date_rejected(self, client):
        p = (await _make_profile(client, "E-CHG2")).json()
        resp = await client.post("/api/hr/changes", json={
            "employee_id": p["id"], "change_type": "transfer",
            "effective_date": "2020-01-01",
        }, headers=H)
        assert resp.status_code == 400

    async def test_resign_workflow_marks_left(self, client):
        p = (await _make_profile(client, "E-RESIGN")).json()
        c = (await client.post("/api/hr/changes", json={
            "employee_id": p["id"], "change_type": "resign",
            "effective_date": "2026-09-20",
        }, headers=H)).json()
        await client.patch(f"/api/hr/changes/{c['id']}/transition",
                           json={"action": "approve"}, headers=H)
        done = await client.patch(f"/api/hr/changes/{c['id']}/transition",
                                  json={"action": "complete"}, headers=H)
        assert done.json()["status"] == "completed"
        prof = await client.get(f"/api/hr/profiles/{p['id']}", headers=H)
        assert prof.json()["status"] == "left"

    async def test_change_invalid_transition(self, client):
        p = (await _make_profile(client, "E-CHG3")).json()
        c = (await client.post("/api/hr/changes", json={
            "employee_id": p["id"], "change_type": "transfer",
            "effective_date": "2026-09-20",
        }, headers=H)).json()
        # draft 不可直接 complete
        resp = await client.patch(f"/api/hr/changes/{c['id']}/transition",
                                  json={"action": "complete"}, headers=H)
        assert resp.status_code == 409


# ═══════════════════════════════════════════════════════════
# 请假
# ═══════════════════════════════════════════════════════════
class TestLeave:
    async def test_create_leave(self, client):
        p = (await _make_profile(client, "E-LEAVE")).json()
        resp = await client.post("/api/hr/leaves", json={
            "employee_id": p["id"], "leave_type": "annual",
            "start_date": "2026-10-01", "end_date": "2026-10-03",
            "days": 3.0, "reason": "年假",
        }, headers=H)
        assert resp.status_code == 201
        assert resp.json()["status"] == "draft"

    async def test_leave_date_order_rejected(self, client):
        p = (await _make_profile(client, "E-LEAVE2")).json()
        resp = await client.post("/api/hr/leaves", json={
            "employee_id": p["id"], "leave_type": "personal",
            "start_date": "2026-10-05", "end_date": "2026-10-01", "days": 1,
        }, headers=H)
        assert resp.status_code == 400

    async def test_leave_approve(self, client):
        p = (await _make_profile(client, "E-LEAVE3")).json()
        leave = (await client.post("/api/hr/leaves", json={
            "employee_id": p["id"], "leave_type": "sick",
            "start_date": "2026-10-01", "end_date": "2026-10-02", "days": 1.5,
        }, headers=H)).json()
        resp = await client.patch(f"/api/hr/leaves/{leave['id']}/transition",
                                  json={"action": "approve"}, headers=H)
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    async def test_leave_double_approve_rejected(self, client):
        p = (await _make_profile(client, "E-LEAVE4")).json()
        leave = (await client.post("/api/hr/leaves", json={
            "employee_id": p["id"], "leave_type": "sick",
            "start_date": "2026-10-01", "end_date": "2026-10-02", "days": 1,
        }, headers=H)).json()
        await client.patch(f"/api/hr/leaves/{leave['id']}/transition",
                           json={"action": "approve"}, headers=H)
        resp = await client.patch(f"/api/hr/leaves/{leave['id']}/transition",
                                  json={"action": "approve"}, headers=H)
        assert resp.status_code == 409

    async def test_leave_list_pagination(self, client):
        resp = await client.get("/api/hr/leaves?limit=5&offset=0", headers=H)
        assert resp.status_code == 200
        assert "total" in resp.json() and "items" in resp.json()
