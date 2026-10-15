from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, case, cast, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Project, Task, User
from app.schemas import TaskCreate, TaskPage, TaskPublic, TaskStats, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])


def ensure_project(db: Session, user_id: int, project_id: int | None) -> None:
    if project_id is not None and db.scalar(select(Project.id).where(Project.id == project_id, Project.owner_id == user_id)) is None:
        raise HTTPException(status_code=404, detail="Project not found.")


@router.post("", response_model=TaskPublic, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_project(db, user.id, payload.project_id)
    values = payload.model_dump()
    if values["status"] == "done":
        values["completed_at"] = datetime.now(timezone.utc)
    task = Task(owner_id=user.id, **values)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("", response_model=TaskPage)
def list_tasks(
    status_filter: Literal["todo", "in_progress", "done"] | None = Query(default=None, alias="status"),
    priority: Literal["low", "medium", "high", "urgent"] | None = None,
    project_id: int | None = None,
    tag: str | None = Query(default=None, min_length=1, max_length=40),
    search: str | None = Query(default=None, min_length=1, max_length=200),
    due_before: datetime | None = None,
    sort: Literal["created", "due", "priority", "title"] = "created",
    direction: Literal["asc", "desc"] = "desc",
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Task).where(Task.owner_id == user.id)
    if status_filter: query = query.where(Task.status == status_filter)
    if priority: query = query.where(Task.priority == priority)
    if project_id is not None: query = query.where(Task.project_id == project_id)
    if tag: query = query.where(cast(Task.tags, String).like(f'%"{tag.strip().lower()}"%'))
    if search:
        needle = f"%{search.strip()}%"
        query = query.where(Task.title.ilike(needle) | Task.description.ilike(needle))
    if due_before: query = query.where(Task.due_at <= due_before)
    sort_columns = {
        "created": Task.created_at,
        "due": Task.due_at,
        "priority": case((Task.priority == "urgent", 0), (Task.priority == "high", 1), (Task.priority == "medium", 2), else_=3),
        "title": Task.title,
    }
    column = sort_columns[sort]
    query = query.order_by(column.asc() if direction == "asc" else column.desc(), Task.id.desc())
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    items = list(db.scalars(query.offset(offset).limit(limit)).all())
    return TaskPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/stats", response_model=TaskStats)
def task_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    today = datetime.now(timezone.utc)
    rows = db.execute(select(Task.status, func.count(Task.id)).where(Task.owner_id == user.id).group_by(Task.status)).all()
    counts = {key: value for key, value in rows}
    overdue = db.scalar(select(func.count(Task.id)).where(Task.owner_id == user.id, Task.status != "done", Task.due_at < today)) or 0
    return TaskStats(total=sum(counts.values()), todo=counts.get("todo", 0), in_progress=counts.get("in_progress", 0), done=counts.get("done", 0), overdue=overdue)


@router.get("/{task_id}", response_model=TaskPublic)
def get_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = db.scalar(select(Task).where(Task.id == task_id, Task.owner_id == user.id))
    if task is None: raise HTTPException(status_code=404, detail="Task not found.")
    return task


@router.patch("/{task_id}", response_model=TaskPublic)
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = db.scalar(select(Task).where(Task.id == task_id, Task.owner_id == user.id))
    if task is None: raise HTTPException(status_code=404, detail="Task not found.")
    values = payload.model_dump(exclude_unset=True)
    for key in ("title", "description", "status", "priority", "tags"):
        if key in values and values[key] is None:
            raise HTTPException(status_code=422, detail=f"{key} cannot be null.")
    if "project_id" in values: ensure_project(db, user.id, values["project_id"])
    if values.get("status") == "done" and task.status != "done":
        task.completed_at = datetime.now(timezone.utc)
    elif values.get("status") is not None and values["status"] != "done":
        task.completed_at = None
    for key, value in values.items(): setattr(task, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Task update conflicts with stored data.")
    db.refresh(task)
    return task


@router.post("/{task_id}/complete", response_model=TaskPublic)
def complete_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = db.scalar(select(Task).where(Task.id == task_id, Task.owner_id == user.id))
    if task is None: raise HTTPException(status_code=404, detail="Task not found.")
    task.status = "done"
    task.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = db.scalar(select(Task).where(Task.id == task_id, Task.owner_id == user.id))
    if task is None: raise HTTPException(status_code=404, detail="Task not found.")
    db.delete(task)
    db.commit()
