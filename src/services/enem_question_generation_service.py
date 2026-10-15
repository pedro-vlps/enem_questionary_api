import json
from typing import Any

from openai import OpenAI
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.helpers.enem_question_common import validate_generated_question_payload
from src.models.models import Questions
from src.services.question_asset_service import (
    get_question_assets_by_ids,
    normalize_question_assets,
)
from src.services.question_service import QuestionService
from src.configs.configs import settings


async def generate_enem_question(
    topic: str,
    build_context_fn,
    build_prompt_fn,
    db: AsyncSession,
    *,
    max_attempts: int = 4,
) -> dict:
    if not settings.QUESTION_GENERATION_ENABLED:
        return await QuestionService.get_random_question(topic=topic, db=db)

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    last_error = None
    selected_context = build_context_fn(topic)

    for _ in range(max_attempts):
        response = client.responses.create(
            model=settings.OPENAI_TEXT_MODEL,
            input=build_prompt_fn(**selected_context),
        )
        response_text = response.output[0].content[0].text

        try:
            payload = json.loads(response_text)
        except json.JSONDecodeError:
            last_error = ValueError("AI response is not a valid JSON object.")
            continue

        validation_error = validate_generated_question_payload(payload)
        if validation_error is not None:
            last_error = ValueError(validation_error)
            continue

        payload.update(selected_context)
        question_assets = normalize_question_assets(payload["question_assets"])
        question = Questions(
            topic=payload["topic"],
            subtopic=payload["subtopic"],
            subtopic_description=payload["subtopic_description"],
            diversity_mode=payload["diversity_mode"],
            question=payload["question"],
            answer_a=payload["answer_a"],
            answer_b=payload["answer_b"],
            answer_c=payload["answer_c"],
            answer_d=payload["answer_d"],
            answer_e=payload["answer_e"],
            explanation_a=payload["explanation_a"],
            explanation_b=payload["explanation_b"],
            explanation_c=payload["explanation_c"],
            explanation_d=payload["explanation_d"],
            explanation_e=payload["explanation_e"],
            correct_answer=payload["correct_answer"],
        )
        result = await QuestionService.persist_question(
            question=question,
            question_assets=question_assets,
            db=db,
        )
        return {**result, "question_source": "api"}

    raise last_error or ValueError("Unable to generate a valid ENEM question.")


async def generate_enem_question_with_support_materials(
    topic: str,
    support_material_ids: list,
    build_context_fn,
    build_prompt_fn,
    db: AsyncSession,
    *,
    max_attempts: int = 4,
) -> dict[str, Any]:
    if not settings.QUESTION_GENERATION_ENABLED:
        return await QuestionService.get_random_question(
            topic=topic, db=db, support_material_ids=support_material_ids
        )

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    last_error = None
    selected_context = build_context_fn(topic)
    support_materials = await get_question_assets_by_ids(
        asset_ids=support_material_ids,
        db=db,
    )

    if not support_materials:
        raise HTTPException(
            status_code=400,
            detail="At least one support material must be provided.",
        )

    for _ in range(max_attempts):
        response = client.responses.create(
            model=settings.OPENAI_TEXT_MODEL,
            input=build_prompt_fn(
                **selected_context,
                forced_question_assets=support_materials,
            ),
        )
        response_text = response.output[0].content[0].text

        try:
            payload = json.loads(response_text)
        except json.JSONDecodeError:
            last_error = ValueError("AI response is not a valid JSON object.")
            continue

        validation_error = validate_generated_question_payload(
            payload,
            require_question_assets=False,
        )
        if validation_error is not None:
            last_error = ValueError(validation_error)
            continue

        payload.update(selected_context)
        question = Questions(
            topic=payload["topic"],
            subtopic=payload["subtopic"],
            subtopic_description=payload["subtopic_description"],
            diversity_mode=payload["diversity_mode"],
            question=payload["question"],
            answer_a=payload["answer_a"],
            answer_b=payload["answer_b"],
            answer_c=payload["answer_c"],
            answer_d=payload["answer_d"],
            answer_e=payload["answer_e"],
            explanation_a=payload["explanation_a"],
            explanation_b=payload["explanation_b"],
            explanation_c=payload["explanation_c"],
            explanation_d=payload["explanation_d"],
            explanation_e=payload["explanation_e"],
            correct_answer=payload["correct_answer"],
        )
        result = await QuestionService.persist_question_with_existing_assets(
            question=question,
            existing_assets=support_materials,
            db=db,
        )
        return {**result, "question_source": "api"}

    raise last_error or ValueError("Unable to generate a valid ENEM question.")
