from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.shopping import (
    ShoppingListBulkDeleteRequest,
    ShoppingListBulkDeleteResponse,
    ShoppingListCreateFromPlanRequest,
    ShoppingListItemRead,
    ShoppingListItemUpdate,
    ShoppingListMergeRequest,
    ShoppingListRead,
    ShoppingListSummaryRead,
    ShoppingManualItemCreate,
)
from app.services.shopping import (
    ShoppingItemUpdateForbiddenError,
    ShoppingListItemNotFoundError,
    ShoppingListNotFoundError,
    ShoppingListSourceNotSupportedError,
    ShoppingPlanNotFoundError,
    add_manual_item,
    create_shopping_list_from_plan,
    delete_shopping_list,
    delete_shopping_lists,
    delete_shopping_list_item,
    get_shopping_list,
    list_shopping_lists,
    merge_shopping_lists,
    rebuild_shopping_list_from_sources,
    update_shopping_list_item,
)

router = APIRouter(prefix="/shopping-lists", tags=["shopping-lists"])


@router.get("", response_model=list[ShoppingListSummaryRead])
def get_shopping_lists(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_shopping_lists(db, current_user.id)


@router.post("/from-plan", response_model=ShoppingListRead, status_code=status.HTTP_201_CREATED)
def post_shopping_list_from_plan(
    payload: ShoppingListCreateFromPlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return create_shopping_list_from_plan(db, current_user.id, payload)
    except ShoppingPlanNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found") from exc


@router.post("/merge", response_model=ShoppingListRead, status_code=status.HTTP_201_CREATED)
def post_merge_shopping_lists(
    payload: ShoppingListMergeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return merge_shopping_lists(db, current_user.id, payload)
    except ShoppingListNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shopping list not found") from exc
    except ShoppingPlanNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found") from exc


@router.post("/bulk-delete", response_model=ShoppingListBulkDeleteResponse)
def post_bulk_delete_shopping_lists(
    payload: ShoppingListBulkDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return delete_shopping_lists(db, current_user.id, payload)
    except ShoppingListNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shopping list not found") from exc


@router.get("/{shopping_list_id}", response_model=ShoppingListRead)
def get_shopping_list_by_id(
    shopping_list_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return get_shopping_list(db, current_user.id, shopping_list_id)
    except ShoppingListNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shopping list not found") from exc


@router.delete("/{shopping_list_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shopping_list_by_id(
    shopping_list_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        delete_shopping_list(db, current_user.id, shopping_list_id)
    except ShoppingListNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shopping list not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{shopping_list_id}/rebuild", response_model=ShoppingListRead)
def post_rebuild_shopping_list(
    shopping_list_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return rebuild_shopping_list_from_sources(db, current_user.id, shopping_list_id)
    except ShoppingListNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shopping list not found") from exc
    except ShoppingPlanNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found") from exc
    except ShoppingListSourceNotSupportedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.patch("/{shopping_list_id}/items/{item_id}", response_model=ShoppingListItemRead)
def patch_shopping_list_item(
    shopping_list_id: int,
    item_id: int,
    payload: ShoppingListItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return update_shopping_list_item(db, current_user.id, shopping_list_id, item_id, payload)
    except ShoppingListNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shopping list not found") from exc
    except ShoppingListItemNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shopping list item not found") from exc
    except ShoppingItemUpdateForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{shopping_list_id}/items/manual", response_model=ShoppingListItemRead, status_code=status.HTTP_201_CREATED)
def post_manual_shopping_item(
    shopping_list_id: int,
    payload: ShoppingManualItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return add_manual_item(db, current_user.id, shopping_list_id, payload)
    except ShoppingListNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shopping list not found") from exc


@router.delete("/{shopping_list_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shopping_item(
    shopping_list_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        delete_shopping_list_item(db, current_user.id, shopping_list_id, item_id)
    except ShoppingListNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shopping list not found") from exc
    except ShoppingListItemNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shopping list item not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
