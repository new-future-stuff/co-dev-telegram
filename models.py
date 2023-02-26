from typing import List, Optional
from sqlmodel import Relationship, SQLModel, Field


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_id: int

    created_projects: List["Project"] = Relationship(back_populates="creator")

    likes_sent: List["UserLike"] = Relationship(back_populates="sender")
    likes_received: List["UserLike"] = Relationship(back_populates="receiver")


class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: str
    creator_id: int = Field(foreign_key="user.id")

    creator: User = Relationship(back_populates="created_projects")

    likes_sent: List["ProjectLike"] = Relationship(back_populates="sender")
    likes_received: List["ProjectLike"] = Relationship(back_populates="receiver")


class ProjectLike(SQLModel, table=True):
    sender_id: int = Field(foreign_key="project.id", primary_key=True)
    receiver_id: int = Field(foreign_key="user.id", primary_key=True)

    sender: Project = Relationship(back_populates="likes_sent")
    receiver: User = Relationship(back_populates="likes_received")


class UserLike(SQLModel, table=True):
    sender_id: int = Field(foreign_key="user.id", primary_key=True)
    receiver_id: int = Field(foreign_key="project.id", primary_key=True)

    sender: User = Relationship(back_populates="likes_sent")
    receiver: Project = Relationship(back_populates="likes_received")
