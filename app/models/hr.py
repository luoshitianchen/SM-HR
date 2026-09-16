"""HR 域模型：员工档案、考勤记录、入转调离异动单、请假单。"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class EmployeeProfile(Base):
    """员工档案：一人一档，工号唯一。"""

    __tablename__ = "hr_employee_profiles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    emp_no: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    department: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    position: Mapped[str] = mapped_column(String(64), default="")
    phone: Mapped[str] = mapped_column(String(32), default="")
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    # 在职状态：probation 试用期 / regular 正式 / left 离职
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="probation", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AttendanceRecord(Base):
    """考勤记录：同一员工同一天唯一一条。"""

    __tablename__ = "hr_attendance_records"
    __table_args__ = (UniqueConstraint("employee_id", "att_date", name="uq_attendance_emp_date"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    employee_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("hr_employee_profiles.id"), nullable=False, index=True
    )
    att_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    # 出勤状态：present 出勤 / late 迟到 / absent 缺勤 / leave 请假
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="present")
    check_in: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_out: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remark: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChangeRequest(Base):
    """入转调离异动单：入职/调动/晋升/离职。"""

    __tablename__ = "hr_change_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    employee_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("hr_employee_profiles.id"), nullable=False, index=True
    )
    # 异动类型：join 入职 / transfer 调动 / promotion 晋升 / resign 离职
    change_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    from_department: Mapped[str] = mapped_column(String(64), default="")
    to_department: Mapped[str] = mapped_column(String(64), default="")
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LeaveRequest(Base):
    """请假单：事假/病假/年假。"""

    __tablename__ = "hr_leave_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    employee_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("hr_employee_profiles.id"), nullable=False, index=True
    )
    leave_type: Mapped[str] = mapped_column(String(16), nullable=False)  # personal/sick/annual
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    days: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
