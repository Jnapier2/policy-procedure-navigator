from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    user_id: str = "ava.employee"


class ReviewCreateRequest(BaseModel):
    query_run_id: str
    user_id: str


class ReviewUpdateRequest(BaseModel):
    user_id: str
    status: Literal["pending_review", "in_review", "approved", "rejected", "completed"]
    decision_note: str | None = Field(default=None, max_length=2000)


class FeedbackRequest(BaseModel):
    query_run_id: str
    user_id: str
    rating: Literal[-1, 1]
    correction: str | None = Field(default=None, max_length=3000)
