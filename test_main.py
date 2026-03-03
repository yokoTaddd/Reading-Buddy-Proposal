import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app, get_db
from database import Base
import os

from sqlalchemy.pool import StaticPool

# Setup test DB
SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}, 
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("test.db"):
        os.remove("test.db")


def test_register_and_login():
    # Register Big Buddy
    res = client.post("/register", json={"username": "big1", "password": "pw1", "role": "big_buddy"})
    assert res.status_code == 200
    assert res.json()["username"] == "big1"

    # Login Big Buddy
    res = client.post("/token", data={"username": "big1", "password": "pw1"})
    assert res.status_code == 200
    token = res.json()["access_token"]
    assert token == "big1"

def test_pairing_flow():
    # Register both
    client.post("/register", json={"username": "big1", "password": "pw1", "role": "big_buddy"})
    client.post("/register", json={"username": "little1", "password": "pw2", "role": "little_buddy"})
    
    # Generate code
    res = client.post("/pair/generate", headers={"Authorization": "Bearer big1"})
    assert res.status_code == 200
    code = res.json()["pairing_code"]
    
    # Join code
    res = client.post("/pair/join", headers={"Authorization": "Bearer little1"}, json={"pairing_code": code})
    assert res.status_code == 200

def test_reading_log():
    # Setup users and pair
    client.post("/register", json={"username": "big1", "password": "pw1", "role": "big_buddy"})
    client.post("/register", json={"username": "little1", "password": "pw2", "role": "little_buddy"})
    res = client.post("/pair/generate", headers={"Authorization": "Bearer big1"})
    code = res.json()["pairing_code"]
    client.post("/pair/join", headers={"Authorization": "Bearer little1"}, json={"pairing_code": code})

    # Add book
    res = client.post("/books/", headers={"Authorization": "Bearer big1"}, json={"book_title": "The Hobbit", "status": "reading"})
    assert res.status_code == 200
    book_id = res.json()["id"]

    # List books
    res = client.get("/books/", headers={"Authorization": "Bearer little1"})
    assert res.status_code == 200
    assert len(res.json()) == 1

    # Update book
    res = client.put(f"/books/{book_id}", headers={"Authorization": "Bearer little1"}, json={"status": "completed"})
    assert res.status_code == 200
    assert res.json()["status"] == "completed"

def test_vocabulary_flow():
    # Setup
    client.post("/register", json={"username": "big1", "password": "pw1", "role": "big_buddy"})
    client.post("/register", json={"username": "little1", "password": "pw2", "role": "little_buddy"})
    res = client.post("/pair/generate", headers={"Authorization": "Bearer big1"})
    code = res.json()["pairing_code"]
    client.post("/pair/join", headers={"Authorization": "Bearer little1"}, json={"pairing_code": code})

    # Upload mock audio
    mock_audio = b"fake-audio-data"
    res = client.post(
        "/vocabulary/?word=apple", 
        headers={"Authorization": "Bearer big1"}, 
        files={"audio_file": ("test.webm", mock_audio, "audio/webm")}
    )
    assert res.status_code == 200
    word_id = res.json()["id"]

    # List vocab as little buddy
    res = client.get("/vocabulary/", headers={"Authorization": "Bearer little1"})
    assert res.status_code == 200
    assert len(res.json()) == 1

    # Fetch audio
    res_audio = client.get(f"/audio/{word_id}", headers={"Authorization": "Bearer little1"})
    assert res_audio.status_code == 200
    assert res_audio.content == mock_audio
