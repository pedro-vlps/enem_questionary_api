from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.models import QuestionAssetQuestions, QuestionAssets, Questions
from src.schemas.question_schema import CreateQuestionRequest
from src.services.question_asset_service import (
    build_question_assets,
    normalize_question_assets,
    serialize_question_asset,
)


class QuestionService:
    @staticmethod
    async def get_random_question(
        *,
        topic: str,
        db: AsyncSession,
        support_material_ids: list[UUID] | None = None,
    ) -> dict[str, Any]:
        query = select(Questions).where(Questions.topic == topic)
        # Every selected material must already be linked to the stored question.
        for asset_id in set(support_material_ids or []):
            query = query.where(
                select(QuestionAssetQuestions.question_id)
                .where(
                    QuestionAssetQuestions.question_id == Questions.id,
                    QuestionAssetQuestions.question_asset_id == asset_id,
                )
                .exists()
            )

        result = await db.execute(query.order_by(func.random()).limit(1))
        question = result.scalar_one_or_none()
        if question is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "No stored question is available for this topic"
                    + (
                        " and the selected support materials"
                        if support_material_ids
                        else ""
                    )
                    + ". AI question generation is disabled."
                ),
            )

        assets_result = await db.execute(
            select(QuestionAssets)
            .join(QuestionAssetQuestions)
            .where(QuestionAssetQuestions.question_id == question.id)
            .order_by(QuestionAssets.display_order)
        )
        payload = QuestionService.serialize_question(
            question, list(assets_result.scalars().all())
        )
        return {**payload, "question_source": "database"}

    @staticmethod
    async def create_question(
        request: CreateQuestionRequest,
        db: AsyncSession,
    ) -> dict[str, Any]:
        payload = request.model_dump()
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

        return await QuestionService.persist_question(
            question=question,
            question_assets=question_assets,
            db=db,
        )

    @staticmethod
    async def persist_question(
        *,
        question: Questions,
        question_assets: list[dict[str, Any]],
        db: AsyncSession,
    ) -> dict[str, Any]:
        db.add(question)
        await db.flush()

        assets = build_question_assets(question.id, question_assets)
        for asset in assets:
            db.add(asset)

        await db.flush()
        for asset in assets:
            db.add(
                QuestionAssetQuestions(
                    question_id=question.id,
                    question_asset_id=asset.id,
                )
            )
        await db.flush()
        await db.commit()
        await db.refresh(question)

        return QuestionService.serialize_question(question, assets)

    @staticmethod
    async def persist_question_with_existing_assets(
        *,
        question: Questions,
        existing_assets: list[QuestionAssets],
        db: AsyncSession,
    ) -> dict[str, Any]:
        db.add(question)
        await db.flush()

        for asset in existing_assets:
            db.add(
                QuestionAssetQuestions(
                    question_id=question.id,
                    question_asset_id=asset.id,
                )
            )
        await db.flush()
        await db.commit()
        await db.refresh(question)

        return QuestionService.serialize_question(question, existing_assets)

    @staticmethod
    def serialize_question(question: Questions, assets: list) -> dict[str, Any]:
        return {
            "id": question.id,
            "topic": question.topic,
            "subtopic": question.subtopic,
            "subtopic_description": question.subtopic_description,
            "diversity_mode": question.diversity_mode,
            "question": question.question,
            "answer_a": question.answer_a,
            "answer_b": question.answer_b,
            "answer_c": question.answer_c,
            "answer_d": question.answer_d,
            "answer_e": question.answer_e,
            "explanation_a": question.explanation_a,
            "explanation_b": question.explanation_b,
            "explanation_c": question.explanation_c,
            "explanation_d": question.explanation_d,
            "explanation_e": question.explanation_e,
            "correct_answer": question.correct_answer,
            "created_at": question.created_at,
            "question_assets": [
                serialize_question_asset(asset)
                for asset in sorted(assets, key=lambda item: item.display_order)
            ],
        }
