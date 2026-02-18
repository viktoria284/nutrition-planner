from fastapi import FastAPI

from dotenv import load_dotenv
load_dotenv("../.env")

app = FastAPI(title="Nutrition Planner API", version="0.1.0")

from app.api.routes import api_router
app.include_router(api_router)

@app.get("/health")
def health():
    return {"status": "ok"}


from fastapi import Depends
from app.api.permissions import require_user, require_admin

@app.get("/protected/user")
def protected_user(u=Depends(require_user)):
    return {"ok": True, "email": u.email, "role": u.role}

@app.get("/protected/admin")
def protected_admin(u=Depends(require_admin)):
    return {"ok": True, "email": u.email, "role": u.role}


from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
