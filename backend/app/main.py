from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.permissions import require_admin, require_user
from app.api.routes import api_router
from app.services.media import get_media_root

load_dotenv("../.env")

app = FastAPI(title="Nutrition Planner API", version="0.1.0")

media_root = get_media_root()
media_root.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(Path(media_root))), name="media")

app.include_router(api_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/protected/user")
def protected_user(u=Depends(require_user)):
    return {"ok": True, "email": u.email, "role": u.role}


@app.get("/protected/admin")
def protected_admin(u=Depends(require_admin)):
    return {"ok": True, "email": u.email, "role": u.role}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
