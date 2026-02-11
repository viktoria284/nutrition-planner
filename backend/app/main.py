from fastapi import FastAPI

from dotenv import load_dotenv
load_dotenv("../.env")

app = FastAPI(title="Nutrition Planner API", version="0.1.0")

from app.api.routes.auth import router as auth_router
app.include_router(auth_router)

@app.get("/health")
def health():
    return {"status": "ok"}
