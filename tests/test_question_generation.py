"""Cost-control regression tests. Run with python -m unittest discover -s tests."""

import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

# Import the application with isolated, non-secret settings, without a local .env.
test_env = {}
for line in Path(".env.example").read_text().splitlines():
    if "=" in line:
        key, value = line.split("=", 1)
        test_env[key] = value or "test"
for key in (
    "POSTGRES_PORT",
    "JWT_EXPIRATION_MINUTES",
    "PASSWORD_RESET_TOKEN_EXPIRATION_MINUTES",
    "SMTP_PORT",
):
    test_env[key] = "5432"
for key in (
    "PASSWORD_RESET_INCLUDE_TOKEN_IN_RESPONSE",
    "SMTP_ENABLED",
    "SMTP_USE_TLS",
    "SMTP_USE_SSL",
):
    test_env[key] = "false"
test_env["OPENAI_API_KEY"] = ""

with patch.dict(os.environ, test_env):
    from src.configs.configs import Settings, settings
    from src.models.models import QuestionAssets, Questions
    from src.services import enem_question_generation_service as generation
    from src.services.question_service import QuestionService


class GenerationTests(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_paths_never_call_openai_or_persist(self):
        for with_materials in (False, True):
            with self.subTest(with_materials=with_materials):
                db = Mock()
                context = Mock(side_effect=AssertionError("Should not build a prompt"))
                payload = {"question_source": "database"}
                with (
                    patch.object(settings, "QUESTION_GENERATION_ENABLED", False),
                    patch.object(generation, "OpenAI") as client,
                    patch.object(
                        QuestionService,
                        "get_random_question",
                        new_callable=AsyncMock,
                        return_value=payload,
                    ) as lookup,
                ):
                    if with_materials:
                        result = await generation.generate_enem_question_with_support_materials(
                            "Geometry", ["asset-1"], context, Mock(), db
                        )
                        lookup.assert_awaited_once_with(
                            topic="Geometry", db=db, support_material_ids=["asset-1"]
                        )
                    else:
                        result = await generation.generate_enem_question(
                            "Geometry", context, Mock(), db
                        )
                        lookup.assert_awaited_once_with(topic="Geometry", db=db)
                    self.assertEqual(result, payload)
                    client.assert_not_called()
                    context.assert_not_called()
                    self.assertEqual(db.mock_calls, [])

    async def test_enabled_paths_generate_and_report_api_source(self):
        payload = {
            "topic": "Geometry",
            "subtopic": "Areas",
            "subtopic_description": "Area calculation",
            "diversity_mode": "context",
            "question": "A school plans to replace the flooring in a rectangular classroom that is ten meters long and five meters wide. What is the area of this classroom?",
            "correct_answer": "A",
            "question_assets": [
                {
                    "asset_type": "text",
                    "rendering_mode": "inline_text",
                    "position": "before_statement",
                    "content": "Classroom floor plan.",
                }
            ],
        }
        for label in "abcde":
            payload[f"answer_{label}"] = f"Option {label}"
            payload[f"explanation_{label}"] = f"Explanation {label}"
        for with_materials in (False, True):
            with self.subTest(with_materials=with_materials):
                persist_method = (
                    "persist_question_with_existing_assets"
                    if with_materials
                    else "persist_question"
                )
                with (
                    patch.object(settings, "QUESTION_GENERATION_ENABLED", True),
                    patch.object(settings, "OPENAI_API_KEY", "test-key"),
                    patch.object(generation, "OpenAI") as client,
                    patch.object(
                        generation,
                        "get_question_assets_by_ids",
                        new_callable=AsyncMock,
                        return_value=[Mock()],
                    ),
                    patch.object(
                        QuestionService,
                        persist_method,
                        new_callable=AsyncMock,
                        return_value={"id": "saved"},
                    ) as persist,
                ):
                    client.return_value.responses.create.return_value = SimpleNamespace(
                        output=[
                            SimpleNamespace(
                                content=[SimpleNamespace(text=json.dumps(payload))]
                            )
                        ]
                    )
                    context = Mock(
                        return_value={
                            key: payload[key]
                            for key in (
                                "topic",
                                "subtopic",
                                "subtopic_description",
                                "diversity_mode",
                            )
                        }
                    )
                    if with_materials:
                        result = await generation.generate_enem_question_with_support_materials(
                            "Geometry", [uuid4()], context, Mock(), Mock()
                        )
                    else:
                        result = await generation.generate_enem_question(
                            "Geometry", context, Mock(), Mock()
                        )
                    self.assertEqual(result["question_source"], "api")
                    client.assert_called_once_with(api_key="test-key")
                    persist.assert_awaited_once()

    async def test_database_returns_question_with_existing_assets_without_writes(self):
        question = Questions(
            id=uuid4(), topic="Geometry", question="Question statement"
        )
        asset = QuestionAssets(
            id=uuid4(),
            asset_type="text",
            rendering_mode="inline_text",
            position="before_statement",
            display_order=0,
            storage_status="not_required",
            content="Previously stored text",
        )
        db = Mock(
            execute=AsyncMock(
                side_effect=[
                    Mock(scalar_one_or_none=Mock(return_value=question)),
                    Mock(
                        scalars=Mock(return_value=Mock(all=Mock(return_value=[asset])))
                    ),
                ]
            )
        )
        result = await QuestionService.get_random_question(topic="Geometry", db=db)
        self.assertEqual(result["id"], question.id)
        self.assertEqual(result["question_source"], "database")
        self.assertEqual(result["question_assets"][0]["id"], asset.id)
        self.assertEqual(
            result["question_assets"][0]["content"], "Previously stored text"
        )
        db.add.assert_not_called()
        db.commit.assert_not_called()
        query = db.execute.call_args_list[0].args[0]
        self.assertIn("Geometry", query.compile().params.values())
        self.assertIn("random()", str(query))

    async def test_empty_database_returns_404_and_requires_all_selected_materials(self):
        from fastapi import HTTPException

        ids = [uuid4(), uuid4()]
        db = Mock(
            execute=AsyncMock(
                return_value=Mock(scalar_one_or_none=Mock(return_value=None))
            )
        )
        with self.assertRaises(HTTPException) as error:
            await QuestionService.get_random_question(
                topic="Geometry", db=db, support_material_ids=ids + ids
            )
        self.assertEqual(error.exception.status_code, 404)
        query = db.execute.call_args.args[0]
        self.assertEqual(str(query).count("EXISTS"), 2)
        for asset_id in ids:
            self.assertIn(asset_id, query.compile().params.values())
        db.execute.assert_awaited_once()

    def test_generation_is_disabled_by_default(self):
        self.assertFalse(Settings.model_fields["QUESTION_GENERATION_ENABLED"].default)


if __name__ == "__main__":
    unittest.main()
