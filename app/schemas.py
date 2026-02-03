from pydantic import BaseModel  # type: ignore
from typing import Optional
from datetime import datetime
from uuid import UUID


class TaskCreate(BaseModel):
    payload: str


class TaskResponse(BaseModel):
    id: UUID
    payload: str
    status: str
    result: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
