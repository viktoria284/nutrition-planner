# Plans + Shopping Smoke Check

## Run
1. Backend:
```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```
2. Frontend:
```bash
cd frontend
npm install
npm run dev
```

## Core Endpoints Used
- `POST /recipes`
- `POST /recipes/{recipe_id}/ingredients`
- `POST /plans`
- `PATCH /plans/{plan_id}/slots/{slot_id}`
- `GET /plans/{plan_id}`
- `GET /plans/{plan_id}/shopping-list`
- `PATCH /plans/{plan_id}/shopping-list/{food_id}`
- `POST /plans/{plan_id}/shopping-list/manual`
- `DELETE /plans/{plan_id}/shopping-list/manual/{manual_item_id}`

## 5-Minute Manual Scenario
1. Create a recipe with at least one ingredient.
2. Create a plan in `/plans/new`.
3. Open `/plans/:id` and set the recipe into a slot.
4. Change slot multiplier (for example from `1` to `1.5`).
5. Verify day totals changed on `/plans/:id`.
6. Open `/plans/:id/shopping`.
7. Toggle `Уже есть` on a computed item.
8. Change grams for the computed item and save.
9. Add one manual item and then delete it via confirm modal.

## Expected Results
- Dates in plan/day columns are stable and do not shift by timezone.
- Slot save updates the plan view after refetch.
- Shopping list reflects slot multiplier and slot recipe changes after refetch.
- `Уже есть`, adjusted grams, and manual item operations do not require page reload.
- Loading/empty/error states are readable and controls are disabled while saving.
- No browser-native `confirm`, `alert`, or tooltip dialogs are used.
