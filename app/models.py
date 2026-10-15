from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    tasks: Mapped[list["Task"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    projects: Mapped[list["Project"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    household_memberships: Mapped[list["HouseholdMember"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Household(Base):
    __tablename__ = "households"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    invite_code: Mapped[str] = mapped_column(String(24), unique=True, index=True, nullable=False)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    memberships: Mapped[list["HouseholdMember"]] = relationship(back_populates="household", cascade="all, delete-orphan")
    lists: Mapped[list["GroceryList"]] = relationship(back_populates="household", cascade="all, delete-orphan")
    family_tasks: Mapped[list["FamilyTask"]] = relationship(back_populates="household", cascade="all, delete-orphan")


class HouseholdMember(Base):
    __tablename__ = "household_members"
    __table_args__ = (UniqueConstraint("household_id", "user_id", name="uq_household_member"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(12), default="member", nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    household: Mapped[Household] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="household_memberships")


class GroceryList(Base):
    __tablename__ = "grocery_lists"
    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    household: Mapped[Household] = relationship(back_populates="lists")
    items: Mapped[list["GroceryItem"]] = relationship(back_populates="grocery_list", cascade="all, delete-orphan")


class GroceryItem(Base):
    __tablename__ = "grocery_items"
    __table_args__ = (Index("ix_grocery_items_list_purchased_priority", "list_id", "is_purchased", "priority"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("grocery_lists.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    category: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    priority: Mapped[str] = mapped_column(String(10), default="normal", nullable=False)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_purchased: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    added_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    purchased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    grocery_list: Mapped[GroceryList] = relationship(back_populates="items")
    added_by: Mapped[User | None] = relationship(foreign_keys=[added_by_id])

    @property
    def added_by_name(self) -> str | None:
        return self.added_by.full_name if self.added_by else None


class FamilyTask(Base):
    __tablename__ = "family_tasks"
    __table_args__ = (Index("ix_family_tasks_household_status_due", "household_id", "status", "due_date"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="todo", nullable=False)
    priority: Mapped[str] = mapped_column(String(10), default="medium", nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    household: Mapped[Household] = relationship(back_populates="family_tasks")
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id])
    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id])


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (Index("ix_projects_owner_name", "owner_id", "name", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    color: Mapped[str] = mapped_column(String(7), default="#64748b", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    owner: Mapped[User] = relationship(back_populates="projects")
    tasks: Mapped[list["Task"]] = relationship(back_populates="project", passive_deletes=True)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_owner_status_due", "owner_id", "status", "due_at"),
        Index("ix_tasks_owner_project", "owner_id", "project_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="todo", index=True, nullable=False)
    priority: Mapped[str] = mapped_column(String(10), default="medium", index=True, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    owner: Mapped[User] = relationship(back_populates="tasks")
    project: Mapped[Project | None] = relationship(back_populates="tasks")
