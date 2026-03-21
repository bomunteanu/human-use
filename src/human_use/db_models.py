import uuid
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import JSON, Column, Text
from sqlmodel import Field, Relationship, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(sa_column=Column(Text, unique=True, nullable=False, index=True))
    hashed_password: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    sessions: List["Session"] = Relationship(back_populates="user")


class Session(SQLModel, table=True):
    __tablename__ = "sessions"

    id: uuid.UUID = Field(primary_key=True)  # frontend-supplied UUID — no default
    user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False, index=True)
    title: str = Field(sa_column=Column(Text, nullable=False))
    brief: Optional[Any] = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    user: Optional[User] = Relationship(back_populates="sessions")
    messages: List["Message"] = Relationship(back_populates="session")


class Message(SQLModel, table=True):
    __tablename__ = "messages"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    session_id: uuid.UUID = Field(foreign_key="sessions.id", nullable=False, index=True)
    role: str = Field(sa_column=Column(Text, nullable=False))
    content: Any = Field(sa_column=Column(JSON, nullable=False))
    order_index: int = Field(nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    session: Optional[Session] = Relationship(back_populates="messages")
