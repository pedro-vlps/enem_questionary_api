from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class QuestionAssetResponse(BaseModel):
    id: UUID
    asset_type: str
    rendering_mode: str
    position: str
    display_order: int
    storage_status: str
    title: str | None = None
    caption: str | None = None
    alt_text: str | None = None
    source_label: str | None = None
    content: str | None = None
    storage_provider: str | None = None
    storage_key: str | None = None
    public_url: str | None = None
    mime_type: str | None = None
    data: dict[str, Any] | None = None


class GeneratedQuestionResponse(BaseModel):
    question_source: Literal["api", "database"] | None = None
    id: UUID
    topic: str
    subtopic: str
    subtopic_description: str
    diversity_mode: str
    question: str
    answer_a: str
    answer_b: str
    answer_c: str
    answer_d: str
    answer_e: str
    explanation_a: str
    explanation_b: str
    explanation_c: str
    explanation_d: str
    explanation_e: str
    correct_answer: str
    created_at: datetime
    question_assets: list[QuestionAssetResponse]

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "12345678-1234-1234-1234-123456789012",
                "topic": "Mathematics",
                "subtopic": "Algebra",
                "subtopic_description": "Solving linear equations",
                "diversity_mode": "balanced",
                "question": "What is the solution to the equation 2x + 3 = 7?",
                "answer_a": "1",
                "answer_b": "2",
                "answer_c": "3",
                "answer_d": "4",
                "answer_e": "5",
                "explanation_a": "The solution is x = 2.",
                "explanation_b": "The solution is x = 3.",
                "explanation_c": "The solution is x = 4.",
                "explanation_d": "The solution is x = 5.",
                "explanation_e": "The solution is x = 6.",
                "correct_answer": "2",
                "created_at": "2023-01-01T00:00:00",
                "question_assets": [],
            }
        },
    )


class GeneratedQuestionGeneric(BaseModel):
    id: UUID
    topic: str
    subtopic: str
    subtopic_description: str
    diversity_mode: str
    question: str
    answer_a: str
    answer_b: str
    answer_c: str
    answer_d: str
    answer_e: str
    explanation_a: str
    explanation_b: str
    explanation_c: str
    explanation_d: str
    explanation_e: str
    correct_answer: str
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "12345678-1234-1234-1234-123456789012",
                "topic": "Mathematics",
                "subtopic": "Algebra",
                "subtopic_description": "Solving linear equations",
                "diversity_mode": "balanced",
                "question": "What is the solution to the equation 2x + 3 = 7?",
                "answer_a": "1",
                "answer_b": "2",
                "answer_c": "3",
                "answer_d": "4",
                "answer_e": "5",
                "explanation_a": "The solution is x = 2.",
                "explanation_b": "The solution is x = 3.",
                "explanation_c": "The solution is x = 4.",
                "explanation_d": "The solution is x = 5.",
                "explanation_e": "The solution is x = 6.",
                "correct_answer": "B",
                "created_at": "2023-01-01T00:00:00",
            }
        },
    )
