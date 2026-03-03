from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base
import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String) # 'big_buddy' or 'little_buddy'

    # Relationships depending on role
    big_pairings = relationship("Pairing", foreign_keys="[Pairing.big_buddy_id]", back_populates="big_buddy")
    little_pairings = relationship("Pairing", foreign_keys="[Pairing.little_buddy_id]", back_populates="little_buddy")


class Pairing(Base):
    __tablename__ = "pairings"

    id = Column(Integer, primary_key=True, index=True)
    pairing_code = Column(String, unique=True, index=True)
    big_buddy_id = Column(Integer, ForeignKey("users.id"))
    little_buddy_id = Column(Integer, ForeignKey("users.id"))

    big_buddy = relationship("User", foreign_keys=[big_buddy_id], back_populates="big_pairings")
    little_buddy = relationship("User", foreign_keys=[little_buddy_id], back_populates="little_pairings")
    vocabulary_words = relationship("VocabularyWord", back_populates="pairing")
    reading_logs = relationship("ReadingLog", back_populates="pairing")

class VocabularyWord(Base):
    __tablename__ = "vocabulary_words"

    id = Column(Integer, primary_key=True, index=True)
    word = Column(String, index=True)
    audio_path = Column(String)
    pairing_id = Column(Integer, ForeignKey("pairings.id"))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    pairing = relationship("Pairing", back_populates="vocabulary_words")

class ReadingLog(Base):
    __tablename__ = "reading_logs"

    id = Column(Integer, primary_key=True, index=True)
    book_title = Column(String, index=True)
    status = Column(String) # 'reading' or 'completed'
    pairing_id = Column(Integer, ForeignKey("pairings.id"))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    pairing = relationship("Pairing", back_populates="reading_logs")
