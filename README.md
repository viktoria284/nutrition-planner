# Система автоматизированного планирования рациона питания

ВКР «Разработка системы автоматизированного планирования рациона питания».
Проект состоит из backend на FastAPI и frontend на React; PostgreSQL поднимается через Docker Compose.

## Стек
- Backend: FastAPI, SQLAlchemy, Alembic, PostgreSQL
- Frontend: React (Vite), TypeScript
- Docker: используется только для PostgreSQL

## Требования
- Python 3.12+
- Node.js 20+ и npm
- Docker + Docker Compose (v2)

## Быстрый старт (локально)
1. Подготовьте переменные окружения:
```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

2. Запустите PostgreSQL (контейнер `nutrition_db`):
```bash
docker compose up -d
```

3. Запустите backend:
```bash
cd backend
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# Windows (cmd)
.venv\Scripts\activate.bat
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

4. Запустите frontend в отдельном терминале:
```bash
cd frontend
npm install && npm run dev
```

## Переменные окружения
### Backend и PostgreSQL (`.env` в корне)
См. `.env.example`:
```env
POSTGRES_DB=nutrition
POSTGRES_USER=nutrition
POSTGRES_PASSWORD=nutrition
DATABASE_URL=postgresql+psycopg://nutrition:nutrition@localhost:5433/nutrition
JWT_SECRET=change_me_dev_secret
JWT_ALG=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

### Frontend (`frontend/.env`)
См. `frontend/.env.example`:
```env
VITE_API_URL=http://localhost:8000
```

## Полезные ссылки
- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- Healthcheck: `http://localhost:8000/health`

## Команды-шпаргалка
### Docker (из корня)
```bash
docker compose logs -f db
docker compose down
```

### Frontend (из `frontend`)
```bash
npm run lint
npm run build
```
