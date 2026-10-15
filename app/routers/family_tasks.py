from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import get_current_user
from app.models import FamilyTask, Household, HouseholdMember, User
from app.schemas import FamilyTaskCreate, FamilyTaskPublic, FamilyTaskUpdate

router = APIRouter(prefix="/family-tasks", tags=["family tasks"])


def require_household(db: Session, household_id: int, user_id: int) -> None:
    member = db.scalar(select(HouseholdMember.id).where(
        HouseholdMember.household_id == household_id, HouseholdMember.user_id == user_id))
    if member is None:
        raise HTTPException(status_code=404, detail="Household not found.")


def validate_assignee(db: Session, household_id: int, assignee_id: int | None) -> None:
    if assignee_id is not None and db.scalar(select(HouseholdMember.id).where(
        HouseholdMember.household_id == household_id, HouseholdMember.user_id == assignee_id)) is None:
        raise HTTPException(status_code=422, detail="Assignee must be a member of this household.")


def to_public(task: FamilyTask) -> FamilyTaskPublic:
    return FamilyTaskPublic(
        id=task.id, household_id=task.household_id, title=task.title,
        description=task.description, status=task.status, priority=task.priority,
        due_date=task.due_date, assignee_id=task.assignee_id,
        assignee_name=task.assignee.full_name if task.assignee else None,
        created_by_id=task.created_by_id, created_by_name=task.created_by.full_name,
        completed_at=task.completed_at, created_at=task.created_at, updated_at=task.updated_at,
    )


@router.get("/households/{household_id}/tasks", response_model=list[FamilyTaskPublic])
def list_family_tasks(
    household_id: int,
    status_filter: str | None = Query(default=None, alias="status", pattern="^(todo|in_progress|done)$"),
    search: str | None = Query(default=None, min_length=1, max_length=200),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    require_household(db, household_id, user.id)
    query = select(FamilyTask).options(joinedload(FamilyTask.assignee), joinedload(FamilyTask.created_by)).where(
        FamilyTask.household_id == household_id)
    if status_filter:
        query = query.where(FamilyTask.status == status_filter)
    if search:
        needle = f"%{search.strip()}%"
        query = query.where(FamilyTask.title.ilike(needle) | FamilyTask.description.ilike(needle))
    priority_order = case((FamilyTask.priority == "urgent", 0), (FamilyTask.priority == "high", 1),
                          (FamilyTask.priority == "medium", 2), else_=3)
    status_order = case((FamilyTask.status == "done", 1), else_=0)
    tasks = db.scalars(query.order_by(status_order, priority_order, FamilyTask.due_date.asc().nullslast(),
                                      FamilyTask.created_at.desc())).all()
    return [to_public(task) for task in tasks]


@router.get("/households/{household_id}/summary")
def family_task_summary(household_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_household(db, household_id, user.id)
    rows = db.execute(select(FamilyTask.status, func.count(FamilyTask.id)).where(
        FamilyTask.household_id == household_id).group_by(FamilyTask.status)).all()
    counts = {key: value for key, value in rows}
    overdue = db.scalar(select(func.count(FamilyTask.id)).where(
        FamilyTask.household_id == household_id, FamilyTask.status != "done",
        FamilyTask.due_date < datetime.now(timezone.utc).date())) or 0
    return {"total": sum(counts.values()), "todo": counts.get("todo", 0),
            "in_progress": counts.get("in_progress", 0), "done": counts.get("done", 0), "overdue": overdue}


@router.post("/households/{household_id}/tasks", response_model=FamilyTaskPublic, status_code=status.HTTP_201_CREATED)
def create_family_task(household_id: int, payload: FamilyTaskCreate,
                       db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_household(db, household_id, user.id)
    validate_assignee(db, household_id, payload.assignee_id)
    task = FamilyTask(household_id=household_id, created_by_id=user.id, **payload.model_dump())
    if task.status == "done":
        task.completed_at = datetime.now(timezone.utc)
    db.add(task)
    db.commit()
    task = db.scalar(select(FamilyTask).options(joinedload(FamilyTask.assignee),
        joinedload(FamilyTask.created_by)).where(FamilyTask.id == task.id))
    return to_public(task)


@router.patch("/{task_id}", response_model=FamilyTaskPublic)
def update_family_task(task_id: int, payload: FamilyTaskUpdate,
                       db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = db.scalar(select(FamilyTask).join(Household).join(HouseholdMember).options(
        joinedload(FamilyTask.assignee), joinedload(FamilyTask.created_by)).where(
        FamilyTask.id == task_id, HouseholdMember.user_id == user.id))
    if task is None:
        raise HTTPException(status_code=404, detail="Family task not found.")
    values = payload.model_dump(exclude_unset=True)
    for key in ("title", "description", "status", "priority"):
        if key in values and values[key] is None:
            raise HTTPException(status_code=422, detail=f"{key} cannot be null.")
    if "assignee_id" in values:
        validate_assignee(db, task.household_id, values["assignee_id"])
    new_status = values.get("status")
    if new_status == "done" and task.status != "done":
        task.completed_at = datetime.now(timezone.utc)
    elif new_status is not None and new_status != "done":
        task.completed_at = None
    for key, value in values.items():
        setattr(task, key, value)
    db.commit()
    db.refresh(task)
    return to_public(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_family_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = db.scalar(select(FamilyTask).join(Household).join(HouseholdMember).where(
        FamilyTask.id == task_id, HouseholdMember.user_id == user.id))
    if task is None:
        raise HTTPException(status_code=404, detail="Family task not found.")
    db.delete(task)
    db.commit()
