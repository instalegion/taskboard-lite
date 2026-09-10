from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import hashlib
import secrets
import jwt

import models
from database import engine, get_db

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="TaskBoard Lite API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = "taskboard_super_secret_key_change_in_production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

cache_store = {}

# --- Pydantic Schemas ---
class UserRegister(BaseModel):
    email: str
    password: str

class BoardCreate(BaseModel):
    title: str

class BoardUpdate(BaseModel):
    title: str

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    status: Optional[str] = "To Do"

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

# --- Password Hashing (Native SHA256 με Salt) ---
def get_password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    key = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${key}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        salt, key = hashed_password.split("$")
        check_key = hashlib.sha256((salt + plain_password).encode("utf-8")).hexdigest()
        return secrets.compare_digest(key, check_key)
    except Exception:
        return False

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# --- Auth Endpoints ---
@app.post("/auth/register", tags=["Auth"])
def register(user: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = get_password_hash(user.password)
    db_user = models.User(email=user.email, hashed_password=hashed)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"message": "User created successfully"}

@app.post("/auth/login", tags=["Auth"])
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    token = create_access_token(data={"sub": user.email})
    return {"access_token": token, "token_type": "bearer"}

# --- Boards Endpoints ---
@app.post("/boards", tags=["Boards"])
def create_board(board: BoardCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_board = models.Board(title=board.title, owner_id=current_user.id)
    db.add(db_board)
    db.commit()
    db.refresh(db_board)
    return db_board

@app.get("/boards", tags=["Boards"])
def list_boards(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.Board).filter(models.Board.owner_id == current_user.id).all()

# --- Tasks Endpoints ---
@app.post("/boards/{board_id}/tasks", tags=["Tasks"])
def create_task(board_id: int, task: TaskCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    board = db.query(models.Board).filter(models.Board.id == board_id, models.Board.owner_id == current_user.id).first()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    db_task = models.Task(title=task.title, description=task.description, status=task.status, board_id=board_id)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    cache_store.pop(board_id, None)
    return db_task

@app.get("/boards/{board_id}/tasks", tags=["Tasks"])
def get_board_tasks(board_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    board = db.query(models.Board).filter(models.Board.id == board_id, models.Board.owner_id == current_user.id).first()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    return db.query(models.Task).filter(models.Task.board_id == board_id).all()

@app.put("/tasks/{task_id}", tags=["Tasks"])
def update_task(task_id: int, task_data: TaskUpdate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.query(models.Task).join(models.Board).filter(models.Task.id == task_id, models.Board.owner_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task_data.title is not None:
        task.title = task_data.title
    if task_data.description is not None:
        task.description = task_data.description
    if task_data.status is not None:
        task.status = task_data.status
        
    db.commit()
    db.refresh(task)
    cache_store.pop(task.board_id, None)
    return task

@app.put("/boards/{board_id}", tags=["Boards"])
def update_board(board_id: int, payload: BoardUpdate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    board = db.query(models.Board).filter(models.Board.id == board_id, models.Board.owner_id == current_user.id).first()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    board.title = payload.title
    db.commit()
    db.refresh(board)
    return board

@app.delete("/boards/{board_id}", tags=["Boards"])
def delete_board(board_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    board = db.query(models.Board).filter(models.Board.id == board_id, models.Board.owner_id == current_user.id).first()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    
    # Διαγραφή του board (λόγω cascade διαγράφονται αυτόματα και όλα τα tasks του)
    db.delete(board)
    db.commit()
    
    # Καθαρισμός από το cache
    cache_store.pop(board_id, None)
    return {"message": "Board deleted successfully"}

@app.delete("/tasks/{task_id}", tags=["Tasks"])
def delete_task(task_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.query(models.Task).join(models.Board).filter(models.Task.id == task_id, models.Board.owner_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    board_id = task.board_id
    db.delete(task)
    db.commit()
    cache_store.pop(board_id, None)
    return {"message": "Task deleted"}

# --- Stats Endpoint με In-Memory Caching ---
@app.get("/boards/{board_id}/stats", tags=["Stats"])
def get_board_stats(board_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    board = db.query(models.Board).filter(models.Board.id == board_id, models.Board.owner_id == current_user.id).first()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
        
    now = datetime.utcnow()
    if board_id in cache_store:
        cached = cache_store[board_id]
        if cached["expires"] > now:
            return {"source": "cache", "stats": cached["data"]}

    tasks = db.query(models.Task).filter(models.Task.board_id == board_id).all()
    stats = {
        "total": len(tasks),
        "todo": sum(1 for t in tasks if t.status == "To Do"),
        "in_progress": sum(1 for t in tasks if t.status == "In Progress"),
        "done": sum(1 for t in tasks if t.status == "Done"),
    }
    
    cache_store[board_id] = {
        "data": stats,
        "expires": now + timedelta(seconds=60)
    }
    return {"source": "database", "stats": stats}

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def serve_home():
    return FileResponse("static/index.html")