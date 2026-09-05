"""SM HR —— 人力资源管理系统：组织、员工、考勤、请假与薪酬核算。"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field

from app import base

SERVICE = "sm-hr"
VERSION = "3.0.0"
NAME = "SM HR"
DESCRIPTION = "人力资源管理系统：组织、员工、考勤、请假与薪酬核算"
PORT = 8500


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _init() -> None:
    with base.db_ctx() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS departments (
                id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, manager TEXT, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS employees (
                id TEXT PRIMARY KEY, employee_no TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
                department TEXT NOT NULL, position TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'active', joined_at TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS leave_requests (
                id TEXT PRIMARY KEY, employee_id TEXT NOT NULL, leave_type TEXT NOT NULL,
                start_date TEXT NOT NULL, end_date TEXT NOT NULL, days REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending', approver TEXT, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS attendance (
                id TEXT PRIMARY KEY, employee_id TEXT NOT NULL, day TEXT NOT NULL,
                status TEXT NOT NULL, UNIQUE(employee_id, day)
            );
            CREATE TABLE IF NOT EXISTS payroll (
                id TEXT PRIMARY KEY, employee_id TEXT NOT NULL, period TEXT NOT NULL,
                base_salary REAL NOT NULL, bonus REAL NOT NULL DEFAULT 0,
                deductions REAL NOT NULL DEFAULT 0, net_pay REAL NOT NULL, created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_emp_dept ON employees(department, status);
            """
        )


app = base.create_app(
    service=SERVICE, name=NAME, description=DESCRIPTION, version=VERSION, port=PORT,
    dependencies=["sm-iam", "sm-audit-log-center"],
    events=["employee.onboarded", "leave.approved", "payroll.issued"],
    overview_fn=lambda _r: {
        "summary": {
            "employees": base.get_db().execute("SELECT COUNT(*) FROM employees").fetchone()[0],
            "active": base.get_db().execute("SELECT COUNT(*) FROM employees WHERE status='active'").fetchone()[0],
        }
    },
)
_init()


class DepartmentIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    manager: str = Field(default="", max_length=80)


class EmployeeIn(BaseModel):
    employee_no: str = Field(min_length=2, max_length=30)
    name: str = Field(min_length=2, max_length=40)
    department: str = Field(min_length=2, max_length=60)
    position: str = Field(min_length=2, max_length=60)
    email: str = Field(min_length=5, max_length=120)
    joined_at: str = Field(default="", max_length=20)


class LeaveIn(BaseModel):
    employee_id: str = Field(min_length=8)
    leave_type: str = Field(min_length=2, max_length=40)
    start_date: str = Field(min_length=8, max_length=12)
    end_date: str = Field(min_length=8, max_length=12)
    approver: str = Field(default="", max_length=80)


class AttendanceIn(BaseModel):
    employee_id: str = Field(min_length=8)
    day: str = Field(min_length=8, max_length=12)
    status: str = Field(pattern=r"^(present|absent|late|leave)$")


class PayrollIn(BaseModel):
    employee_id: str = Field(min_length=8)
    period: str = Field(min_length=6, max_length=10)
    base_salary: float = Field(ge=0)
    bonus: float = Field(default=0, ge=0)
    deductions: float = Field(default=0, ge=0)


@app.get("/api/hr/departments")
def list_departments() -> dict[str, Any]:
    with base.db_ctx() as conn:
        rows = conn.execute("SELECT * FROM departments ORDER BY created_at DESC").fetchall()
    return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.post("/api/hr/departments", status_code=status.HTTP_201_CREATED)
def create_department(payload: DepartmentIn, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    dept_id = str(uuid.uuid4())
    with base.db_ctx() as conn:
        try:
            conn.execute("INSERT INTO departments VALUES (?,?,?,?)", (dept_id, payload.name, payload.manager, _now()))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status.HTTP_409_CONFLICT, "部门已存在") from exc
    return {"id": dept_id, "name": payload.name}


@app.post("/api/hr/employees", status_code=status.HTTP_201_CREATED)
def onboard_employee(payload: EmployeeIn, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    emp_id = str(uuid.uuid4())
    joined_at = payload.joined_at or date.today().isoformat()
    with base.db_ctx() as conn:
        if not conn.execute("SELECT 1 FROM departments WHERE name=?", (payload.department,)).fetchone():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "部门不存在")
        try:
            conn.execute("INSERT INTO employees VALUES (?,?,?,?,?,?,?,?,?)", (emp_id, payload.employee_no, payload.name, payload.department, payload.position, payload.email, "active", joined_at, _now()))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status.HTTP_409_CONFLICT, "工号或邮箱已存在") from exc
        base.record_audit("employee.onboarded", "internal", f"employee={payload.employee_no}", getattr(request.state, "request_id", ""), getattr(request.state, "trace_id", ""), SERVICE)
    return {"id": emp_id, "employee_no": payload.employee_no, "name": payload.name}


@app.get("/api/hr/employees")
def list_employees(department: str | None = None, status_: str | None = None) -> dict[str, Any]:
    clauses, params = [], []
    if department:
        clauses.append("department=?")
        params.append(department)
    if status_:
        clauses.append("status=?")
        params.append(status_)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with base.db_ctx() as conn:
        rows = conn.execute(f"SELECT * FROM employees{where} ORDER BY joined_at DESC LIMIT 200", params).fetchall()
    return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.get("/api/hr/employees/{emp_id}")
def get_employee(emp_id: str) -> dict[str, Any]:
    with base.db_ctx() as conn:
        row = conn.execute("SELECT * FROM employees WHERE id=?", (emp_id,)).fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "员工不存在")
    return dict(row)


def _calc_days(start: str, end: str) -> float:
    try:
        return (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    except ValueError:
        return 1.0


@app.post("/api/hr/leave", status_code=status.HTTP_201_CREATED)
def submit_leave(payload: LeaveIn, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    leave_id = str(uuid.uuid4())
    days = _calc_days(payload.start_date, payload.end_date)
    with base.db_ctx() as conn:
        if not conn.execute("SELECT 1 FROM employees WHERE id=?", (payload.employee_id,)).fetchone():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "员工不存在")
        conn.execute("INSERT INTO leave_requests (id, employee_id, leave_type, start_date, end_date, days, status, approver, created_at) VALUES (?,?,?,?,?,?,?,?,?)", (leave_id, payload.employee_id, payload.leave_type, payload.start_date, payload.end_date, days, "pending", payload.approver, _now()))
    return {"id": leave_id, "days": days, "status": "pending"}


@app.get("/api/hr/leave")
def list_leave(status_: str | None = None) -> dict[str, Any]:
    with base.db_ctx() as conn:
        if status_:
            rows = conn.execute("SELECT * FROM leave_requests WHERE status=? ORDER BY created_at DESC", (status_,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM leave_requests ORDER BY created_at DESC LIMIT 200").fetchall()
    return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.post("/api/hr/leave/{leave_id}/approve")
def approve_leave(leave_id: str, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    return _decide_leave(leave_id, "approved", request)


@app.post("/api/hr/leave/{leave_id}/reject")
def reject_leave(leave_id: str, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    return _decide_leave(leave_id, "rejected", request)


def _decide_leave(leave_id: str, decision: str, request: Request) -> dict[str, Any]:
    with base.db_ctx() as conn:
        if conn.execute("UPDATE leave_requests SET status=? WHERE id=? AND status='pending'", (decision, leave_id)).rowcount == 0:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "请假单不存在或已处理")
        base.record_audit("leave.approved", "internal", f"leave={leave_id} decision={decision}", getattr(request.state, "request_id", ""), getattr(request.state, "trace_id", ""), SERVICE)
    return {"id": leave_id, "status": decision}


@app.post("/api/hr/attendance")
def record_attendance(payload: AttendanceIn, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    with base.db_ctx() as conn:
        if not conn.execute("SELECT 1 FROM employees WHERE id=?", (payload.employee_id,)).fetchone():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "员工不存在")
        conn.execute("INSERT OR REPLACE INTO attendance (id, employee_id, day, status) VALUES (?,?,?,?)", (str(uuid.uuid4()), payload.employee_id, payload.day, payload.status))
    return {"employee_id": payload.employee_id, "day": payload.day, "status": payload.status}


@app.post("/api/hr/payroll", status_code=status.HTTP_201_CREATED)
def issue_payroll(payload: PayrollIn, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    payroll_id = str(uuid.uuid4())
    net_pay = round(payload.base_salary + payload.bonus - payload.deductions, 2)
    with base.db_ctx() as conn:
        if not conn.execute("SELECT 1 FROM employees WHERE id=?", (payload.employee_id,)).fetchone():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "员工不存在")
        conn.execute("INSERT INTO payroll VALUES (?,?,?,?,?,?,?,?)", (payroll_id, payload.employee_id, payload.period, payload.base_salary, payload.bonus, payload.deductions, net_pay, _now()))
        base.record_audit("payroll.issued", "internal", f"payroll={payroll_id} period={payload.period}", getattr(request.state, "request_id", ""), getattr(request.state, "trace_id", ""), SERVICE)
    return {"id": payroll_id, "period": payload.period, "net_pay": net_pay}


@app.get("/api/hr/stats")
def stats() -> dict[str, Any]:
    with base.db_ctx() as conn:
        def _count(sql: str) -> int:
            return conn.execute(sql).fetchone()[0]
        by_dept = [dict(r) for r in conn.execute("SELECT department, COUNT(*) AS count FROM employees WHERE status='active' GROUP BY department").fetchall()]
        return {
            "employees": _count("SELECT COUNT(*) FROM employees"),
            "active": _count("SELECT COUNT(*) FROM employees WHERE status='active'"),
            "departments": _count("SELECT COUNT(*) FROM departments"),
            "pending_leave": _count("SELECT COUNT(*) FROM leave_requests WHERE status='pending'"),
            "by_department": by_dept,
        }