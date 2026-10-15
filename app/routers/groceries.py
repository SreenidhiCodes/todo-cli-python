from datetime import datetime, timezone
import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import get_current_user
from app.models import GroceryItem, GroceryList, Household, HouseholdMember, User
from app.schemas import (GroceryItemCreate, GroceryItemPublic, GroceryItemUpdate,
                         GroceryListCreate, GroceryListPublic, HouseholdCreate,
                         HouseholdJoin, HouseholdMemberPublic, HouseholdPublic)

router = APIRouter(prefix="/groceries", tags=["groceries"])


def new_invite_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(12))


def require_household(db: Session, household_id: int, user_id: int) -> Household:
    household = db.scalar(select(Household).join(HouseholdMember).where(
        Household.id == household_id, HouseholdMember.user_id == user_id))
    if household is None:
        raise HTTPException(status_code=404, detail="Household not found.")
    return household


def require_list(db: Session, list_id: int, user_id: int) -> GroceryList:
    grocery_list = db.scalar(select(GroceryList).join(Household).join(HouseholdMember).where(
        GroceryList.id == list_id, HouseholdMember.user_id == user_id))
    if grocery_list is None:
        raise HTTPException(status_code=404, detail="Grocery list not found.")
    return grocery_list


@router.get("/households", response_model=list[HouseholdPublic])
def list_households(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return list(db.scalars(select(Household).join(HouseholdMember).where(
        HouseholdMember.user_id == user.id).order_by(Household.name)).all())


@router.post("/households", response_model=HouseholdPublic, status_code=status.HTTP_201_CREATED)
def create_household(payload: HouseholdCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    household = Household(name=payload.name, invite_code=new_invite_code(), created_by_id=user.id)
    db.add(household)
    db.flush()
    db.add(HouseholdMember(household_id=household.id, user_id=user.id, role="owner"))
    db.commit()
    db.refresh(household)
    return household


@router.post("/households/join", response_model=HouseholdPublic)
def join_household(payload: HouseholdJoin, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    household = db.scalar(select(Household).where(Household.invite_code == payload.invite_code.upper()))
    if household is None:
        raise HTTPException(status_code=404, detail="That invite code was not found.")
    membership = db.scalar(select(HouseholdMember).where(
        HouseholdMember.household_id == household.id, HouseholdMember.user_id == user.id))
    if membership is None:
        db.add(HouseholdMember(household_id=household.id, user_id=user.id, role="member"))
        db.commit()
    return household


@router.post("/households/{household_id}/rotate-code", response_model=HouseholdPublic)
def rotate_invite_code(household_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    household = require_household(db, household_id, user.id)
    if household.created_by_id != user.id:
        raise HTTPException(status_code=403, detail="Only the household owner can reset its invite code.")
    household.invite_code = new_invite_code()
    db.commit()
    db.refresh(household)
    return household


@router.get("/households/{household_id}/lists", response_model=list[GroceryListPublic])
def list_grocery_lists(household_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_household(db, household_id, user.id)
    return list(db.scalars(select(GroceryList).where(GroceryList.household_id == household_id).order_by(GroceryList.name)).all())


@router.get("/households/{household_id}/members", response_model=list[HouseholdMemberPublic])
def household_members(household_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_household(db, household_id, user.id)
    rows = db.execute(select(User.id, User.full_name, HouseholdMember.role).join(
        HouseholdMember, HouseholdMember.user_id == User.id).where(
        HouseholdMember.household_id == household_id).order_by(User.full_name)).all()
    return [HouseholdMemberPublic(user_id=row.id, full_name=row.full_name, role=row.role) for row in rows]


@router.post("/households/{household_id}/lists", response_model=GroceryListPublic, status_code=status.HTTP_201_CREATED)
def create_grocery_list(household_id: int, payload: GroceryListCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_household(db, household_id, user.id)
    grocery_list = GroceryList(household_id=household_id, name=payload.name)
    db.add(grocery_list)
    db.commit()
    db.refresh(grocery_list)
    return grocery_list


@router.get("/lists/{list_id}/items", response_model=list[GroceryItemPublic])
def list_items(list_id: int, purchased: str = Query(default="all", pattern="^(all|needed|purchased)$"),
               search: str | None = Query(default=None, min_length=1, max_length=200),
               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_list(db, list_id, user.id)
    query = select(GroceryItem).where(GroceryItem.list_id == list_id)
    if purchased == "needed": query = query.where(GroceryItem.is_purchased.is_(False))
    if purchased == "purchased": query = query.where(GroceryItem.is_purchased.is_(True))
    if search:
        needle = f"%{search.strip()}%"
        query = query.where(GroceryItem.name.ilike(needle) | GroceryItem.category.ilike(needle) | GroceryItem.notes.ilike(needle))
    priority_order = case((GroceryItem.priority == "urgent", 0), (GroceryItem.priority == "high", 1),
                          (GroceryItem.priority == "normal", 2), else_=3)
    return list(db.scalars(query.options(joinedload(GroceryItem.added_by)).order_by(
        GroceryItem.is_purchased.asc(), priority_order, GroceryItem.deadline.asc().nullslast(),
        GroceryItem.created_at.asc())).all())


@router.get("/lists/{list_id}/summary")
def list_summary(list_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_list(db, list_id, user.id)
    today = datetime.now(timezone.utc).date()
    rows = db.execute(select(GroceryItem.is_purchased, func.count(GroceryItem.id)).where(
        GroceryItem.list_id == list_id).group_by(GroceryItem.is_purchased)).all()
    counts = {key: value for key, value in rows}
    overdue = db.scalar(select(func.count(GroceryItem.id)).where(GroceryItem.list_id == list_id,
        GroceryItem.is_purchased.is_(False), GroceryItem.deadline < today)) or 0
    return {"needed": counts.get(False, 0), "purchased": counts.get(True, 0), "overdue": overdue}


@router.post("/lists/{list_id}/items", response_model=GroceryItemPublic, status_code=status.HTTP_201_CREATED)
def create_item(list_id: int, payload: GroceryItemCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_list(db, list_id, user.id)
    item = GroceryItem(list_id=list_id, added_by_id=user.id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/items/{item_id}", response_model=GroceryItemPublic)
def update_item(item_id: int, payload: GroceryItemUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.scalar(select(GroceryItem).join(GroceryList).join(Household).join(HouseholdMember).where(
        GroceryItem.id == item_id, HouseholdMember.user_id == user.id))
    if item is None: raise HTTPException(status_code=404, detail="Grocery item not found.")
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items(): setattr(item, key, value)
    if values.get("is_purchased") is not None:
        item.purchased_at = datetime.now(timezone.utc) if values["is_purchased"] else None
    db.commit()
    db.refresh(item)
    return item


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.scalar(select(GroceryItem).join(GroceryList).join(Household).join(HouseholdMember).where(
        GroceryItem.id == item_id, HouseholdMember.user_id == user.id))
    if item is None: raise HTTPException(status_code=404, detail="Grocery item not found.")
    db.delete(item)
    db.commit()
