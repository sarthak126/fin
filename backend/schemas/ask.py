"""
Shared schemas for conversational ask endpoints.
"""

from __future__ import annotations

from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str


class AskSource(BaseModel):
    section_title: str = ""
    page_num: int = 0


class AskResponse(BaseModel):
    answer: str
    sources: list[AskSource] = []
