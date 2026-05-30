from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import date, datetime
import uuid

class StudentBase(BaseModel):
    name: str
    whatsapp_number: str
    exam_type: Optional[str] = None
    exam_date: Optional[date] = None
    weak_subjects: Optional[List[str]] = []
    daily_schedule: Optional[Dict[str, Any]] = {}
    guardian_contact: Optional[str] = None

class StudentCreate(StudentBase):
    pass

class Student(StudentBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

class TaskBase(BaseModel):
    student_id: uuid.UUID
    title: str
    description: Optional[str] = None
    status: str = "pending"
    due_date: Optional[datetime] = None

class Task(TaskBase):
    id: uuid.UUID
    created_at: datetime

class InteractionBase(BaseModel):
    student_id: uuid.UUID
    direction: str # inbound, outbound
    message_type: str # text, voice
    content: str

class Interaction(InteractionBase):
    id: uuid.UUID
    created_at: datetime

class QuizBase(BaseModel):
    student_id: uuid.UUID
    question: str
    expected_answer: Optional[str] = None

class Quiz(QuizBase):
    id: uuid.UUID
    student_answer: Optional[str] = None
    score: Optional[str] = None
    created_at: datetime
    answered_at: Optional[datetime] = None
