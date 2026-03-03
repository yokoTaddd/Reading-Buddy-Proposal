from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List
import os
import uuid
import uuid
import secrets

import models
import schemas
from database import engine, get_db
from passlib.context import CryptContext

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Reading Buddy API")

# Ensure uploads directory exists
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- Helper Functions ---
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def generate_pairing_code():
    return secrets.token_hex(4).upper() # 8 character hex string

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    # In a real app, this would use JWT. For simplicity of the prototype, 
    # we'll just use the token as the username (insecure, but fine for a quick local prototype)
    # Let's actually implement a basic mock JWT or just look up user by token if we store it.
    # To keep it extremely simple without PyJWT overhead for the prototype:
    # We will assume the token IS the username for this MVP, or we can use PyJWT.
    # Actually, let's use a very simple approach: username is passed as token for auth in testing.
    # In a real app we MUST use PyJWT.
    
    # We'll expect the frontend to pass the username as the bearer token for now
    user = get_user_by_username(db, username=token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

# --- Authentication & User Endpoints ---

@app.post("/register", response_model=schemas.UserDisplay)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    if user.role not in ["big_buddy", "little_buddy"]:
        raise HTTPException(status_code=400, detail="Invalid role. Must be big_buddy or little_buddy")
    
    hashed_password = get_password_hash(user.password)
    new_user = models.User(username=user.username, hashed_password=hashed_password, role=user.role)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/token")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = get_user_by_username(db, username=form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Mock JWT: just return the username as the token
    return {"access_token": user.username, "token_type": "bearer", "role": user.role}

# --- Pairing Endpoints ---

@app.post("/pair/generate", response_model=schemas.PairingDisplay)
def generate_pair_code(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "big_buddy":
        raise HTTPException(status_code=403, detail="Only Big Buddies can generate pairing codes")
    
    code = generate_pairing_code()
    new_pairing = models.Pairing(pairing_code=code, big_buddy_id=current_user.id)
    db.add(new_pairing)
    db.commit()
    db.refresh(new_pairing)
    return new_pairing

@app.post("/pair/join")
def join_pair(req: schemas.PairRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "little_buddy":
        raise HTTPException(status_code=403, detail="Only Little Buddies can join via pairing code")
    
    pairing = db.query(models.Pairing).filter(models.Pairing.pairing_code == req.pairing_code).first()
    if not pairing:
        raise HTTPException(status_code=404, detail="Pairing code not found")
    
    if pairing.little_buddy_id:
         raise HTTPException(status_code=400, detail="This pairing code is already used")

    pairing.little_buddy_id = current_user.id
    db.commit()
    return {"message": "Successfully paired!"}

# --- Vocabulary Endpoints ---

@app.post("/vocabulary/", response_model=schemas.VocabularyWordDisplay)
async def upload_vocabulary(
    word: str,
    audio_file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)):
    
    if current_user.role != "big_buddy":
        raise HTTPException(status_code=403, detail="Only Big Buddies can upload vocabulary")
    
    # Verify pairing
    pairing = db.query(models.Pairing).filter(models.Pairing.big_buddy_id == current_user.id).first()
    if not pairing:
         raise HTTPException(status_code=400, detail="You are not paired with a Little Buddy yet")

    # Save file
    file_extension = audio_file.filename.split(".")[-1]
    filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(await audio_file.read())

    # Save to db
    new_word = models.VocabularyWord(word=word, audio_path=file_path, pairing_id=pairing.id)
    db.add(new_word)
    db.commit()
    db.refresh(new_word)
    return new_word

@app.get("/vocabulary/", response_model=List[schemas.VocabularyWordDisplay])
def list_vocabulary(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Verify pairing based on role
    if current_user.role == "little_buddy":
        pairing = db.query(models.Pairing).filter(models.Pairing.little_buddy_id == current_user.id).first()
    else:
        pairing = db.query(models.Pairing).filter(models.Pairing.big_buddy_id == current_user.id).first()
        
    if not pairing:
         return [] # Not paired yet
    
    words = db.query(models.VocabularyWord).filter(models.VocabularyWord.pairing_id == pairing.id).all()
    return words

from fastapi.responses import FileResponse

@app.get("/audio/{word_id}")
def get_audio(word_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    word = db.query(models.VocabularyWord).filter(models.VocabularyWord.id == word_id).first()
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
        
    # Security: check if user belongs to the pairing of this word
    if current_user.role == "little_buddy":
        pairing = db.query(models.Pairing).filter(models.Pairing.little_buddy_id == current_user.id).first()
    else:
        pairing = db.query(models.Pairing).filter(models.Pairing.big_buddy_id == current_user.id).first()
        
    if not pairing or pairing.id != word.pairing_id:
        raise HTTPException(status_code=403, detail="You don't have access to this audio")

    if not os.path.exists(word.audio_path):
        raise HTTPException(status_code=404, detail="Audio file missing on server")
        
    return FileResponse(word.audio_path)

# --- Reading Log Endpoints ---

@app.post("/books/", response_model=schemas.ReadingLogDisplay)
def add_book(book: schemas.ReadingLogCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role == "little_buddy":
        pairing = db.query(models.Pairing).filter(models.Pairing.little_buddy_id == current_user.id).first()
    else:
        pairing = db.query(models.Pairing).filter(models.Pairing.big_buddy_id == current_user.id).first()
        
    if not pairing:
         raise HTTPException(status_code=400, detail="You must be paired to add to the reading log")

    new_book = models.ReadingLog(book_title=book.book_title, status=book.status, pairing_id=pairing.id)
    db.add(new_book)
    db.commit()
    db.refresh(new_book)
    return new_book

@app.get("/books/", response_model=List[schemas.ReadingLogDisplay])
def list_books(status: str = None, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role == "little_buddy":
        pairing = db.query(models.Pairing).filter(models.Pairing.little_buddy_id == current_user.id).first()
    else:
        pairing = db.query(models.Pairing).filter(models.Pairing.big_buddy_id == current_user.id).first()
        
    if not pairing:
         return []

    query = db.query(models.ReadingLog).filter(models.ReadingLog.pairing_id == pairing.id)
    if status:
        query = query.filter(models.ReadingLog.status == status)
    
    return query.all()

@app.put("/books/{book_id}", response_model=schemas.ReadingLogDisplay)
def update_book_status(book_id: int, book_update: schemas.ReadingLogUpdate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role == "little_buddy":
        pairing = db.query(models.Pairing).filter(models.Pairing.little_buddy_id == current_user.id).first()
    else:
        pairing = db.query(models.Pairing).filter(models.Pairing.big_buddy_id == current_user.id).first()
        
    if not pairing:
         raise HTTPException(status_code=400, detail="You must be paired to update the reading log")

    book = db.query(models.ReadingLog).filter(models.ReadingLog.id == book_id, models.ReadingLog.pairing_id == pairing.id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
        
    book.status = book_update.status
    db.commit()
    db.refresh(book)
    return book

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all for local protoyping
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
