from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
import datetime

# User Schemas
class UserBase(BaseModel):
    username: str
    role: str = Field(description="'big_buddy' or 'little_buddy'")

class UserCreate(UserBase):
    password: str

class UserDisplay(UserBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

# Pairing Schemas
class PairingBase(BaseModel):
    pairing_code: str

class PairingCreate(PairingBase):
    pass

class PairingDisplay(BaseModel):
    id: int
    pairing_code: str
    big_buddy_id: Optional[int]
    little_buddy_id: Optional[int]

    model_config = ConfigDict(from_attributes=True)

class PairRequest(BaseModel):
    pairing_code: str

# Vocabulary Schemas
class VocabularyWordBase(BaseModel):
    word: str

class VocabularyWordDisplay(VocabularyWordBase):
    id: int
    audio_path: str
    pairing_id: int
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)

# Reading Log Schemas
class ReadingLogBase(BaseModel):
    book_title: str
    status: str = Field(description="'reading' or 'completed'")

class ReadingLogCreate(ReadingLogBase):
    pass

class ReadingLogDisplay(ReadingLogBase):
    id: int
    pairing_id: int
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)

class ReadingLogUpdate(BaseModel):
    status: str
