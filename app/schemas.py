from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

TaskStatus = Literal["todo", "in_progress", "done"]
TaskPriority = Literal["low", "medium", "high", "urgent"]
CleanTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class UserCreate(BaseModel):
    email: EmailStr
    full_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    password: Annotated[str, Field(min_length=8, max_length=128)]


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    full_name: str
    is_active: bool
    created_at: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TaskCreate(BaseModel):
    title: CleanTitle
    description: Annotated[str, Field(max_length=10000)] = ""
    status: TaskStatus = "todo"
    priority: TaskPriority = "medium"
    tags: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]] = Field(default_factory=list, max_length=20)
    due_at: datetime | None = None
    project_id: int | None = None

    @field_validator("tags")
    @classmethod
    def unique_tags(cls, tags: list[str]) -> list[str]:
        return list(dict.fromkeys(tag.lower() for tag in tags))


class TaskUpdate(BaseModel):
    title: CleanTitle | None = None
    description: Annotated[str, Field(max_length=10000)] | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    tags: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]] | None = Field(default=None, max_length=20)
    due_at: datetime | None = None
    project_id: int | None = None

    @field_validator("tags")
    @classmethod
    def unique_tags(cls, tags: list[str] | None) -> list[str] | None:
        return list(dict.fromkeys(tag.lower() for tag in tags)) if tags is not None else None


class TaskPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    owner_id: int
    project_id: int | None
    title: str
    description: str
    status: TaskStatus
    priority: TaskPriority
    tags: list[str]
    due_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TaskPage(BaseModel):
    items: list[TaskPublic]
    total: int
    limit: int
    offset: int


class ProjectCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    description: Annotated[str, Field(max_length=5000)] = ""
    color: Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")] = "#64748b"


class ProjectUpdate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)] | None = None
    description: Annotated[str, Field(max_length=5000)] | None = None
    color: Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")] | None = None


class ProjectPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    owner_id: int
    name: str
    description: str
    color: str
    created_at: datetime
    updated_at: datetime


class TaskStats(BaseModel):
    total: int
    todo: int
    in_progress: int
    done: int
    overdue: int


GroceryPriority = Literal["low", "normal", "high", "urgent"]


class HouseholdCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class HouseholdJoin(BaseModel):
    invite_code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=6, max_length=24)]


class HouseholdPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    invite_code: str
    created_by_id: int
    created_at: datetime


class GroceryListCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class GroceryListPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    household_id: int
    name: str
    created_at: datetime
    updated_at: datetime


class GroceryItemCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    quantity: Annotated[str, Field(max_length=80)] = ""
    category: Annotated[str, Field(max_length=80)] = ""
    priority: GroceryPriority = "normal"
    deadline: date | None = None
    notes: Annotated[str, Field(max_length=5000)] = ""


class GroceryItemUpdate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)] | None = None
    quantity: Annotated[str, Field(max_length=80)] | None = None
    category: Annotated[str, Field(max_length=80)] | None = None
    priority: GroceryPriority | None = None
    deadline: date | None = None
    notes: Annotated[str, Field(max_length=5000)] | None = None
    is_purchased: bool | None = None


class GroceryItemPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    list_id: int
    name: str
    quantity: str
    category: str
    priority: GroceryPriority
    deadline: date | None
    notes: str
    is_purchased: bool
    purchased_at: datetime | None
    created_at: datetime
    updated_at: datetime
