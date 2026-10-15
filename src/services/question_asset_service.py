import base64
import binascii
import mimetypes
import re
import uuid
from typing import TYPE_CHECKING, Any

from openai import OpenAI
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.configs.configs import settings
from src.utils.s3_storage import S3Storage

if TYPE_CHECKING:
    from src.models.models import QuestionAssets

SUPPORTED_ASSET_TYPES = {
    "text",
    "table",
    "chart",
    "image",
    "map",
    "diagram",
    "infographic",
}
SUPPORTED_RENDERING_MODES = {"inline_text", "structured_data", "generated_image"}
SUPPORTED_POSITIONS = {"before_statement", "after_statement"}
VISUAL_ASSET_TYPES = {"image", "map", "infographic"}
STRUCTURED_ASSET_TYPES = {"table", "chart", "diagram"}
DATA_URL_PATTERN = re.compile(
    r"^data:(?P<mime>[-\w.+/]+);base64,(?P<data>[A-Za-z0-9+/=\s]+)$"
)


def validate_question_assets(materials: Any) -> str | None:
    if not isinstance(materials, list) or not materials:
        return "AI response must include at least one question asset."

    if len(materials) > 2:
        return "AI response returned more than two question assets."

    for index, raw_material in enumerate(materials, start=1):
        if not isinstance(raw_material, dict):
            return f"Question asset #{index} is not an object."

        asset_type = raw_material.get("asset_type")
        rendering_mode = raw_material.get("rendering_mode")
        position = raw_material.get("position")

        if asset_type not in SUPPORTED_ASSET_TYPES:
            return f"Question asset #{index} has an invalid asset_type."
        if rendering_mode not in SUPPORTED_RENDERING_MODES:
            return f"Question asset #{index} has an invalid rendering_mode."
        if position not in SUPPORTED_POSITIONS:
            return f"Question asset #{index} has an invalid position."

        if asset_type == "text":
            if rendering_mode != "inline_text":
                return (
                    f"Support material #{index} with asset_type text must use "
                    "rendering_mode inline_text."
                )
            if not str(raw_material.get("content", "")).strip():
                return f"Question asset #{index} is missing content."
            continue

        if asset_type in STRUCTURED_ASSET_TYPES:
            if rendering_mode != "structured_data":
                return (
                    f"Support material #{index} with asset_type {asset_type} must use "
                    "rendering_mode structured_data."
                )
            if not isinstance(raw_material.get("data"), dict) or not raw_material.get(
                "data"
            ):
                return f"Question asset #{index} is missing structured data."
            if asset_type == "diagram":
                diagram_type = str(raw_material["data"].get("diagram_type", "")).strip()
                if not diagram_type:
                    return (
                        f"Question asset #{index} with asset_type diagram is missing "
                        "diagram_type."
                    )
            continue

        if asset_type in VISUAL_ASSET_TYPES:
            if rendering_mode != "generated_image":
                return (
                    f"Support material #{index} with asset_type {asset_type} must use "
                    "rendering_mode generated_image."
                )
            visual_sources = sum(
                bool(str(raw_material.get(field, "")).strip())
                for field in ("image_generation_prompt", "public_url", "file_base64")
            )
            if visual_sources != 1:
                return (
                    f"Question asset #{index} must include exactly one visual source: "
                    "image_generation_prompt, public_url or file_base64."
                )
            if not str(raw_material.get("alt_text", "")).strip():
                return f"Question asset #{index} is missing alt_text."
            continue

    return None


def normalize_question_assets(
    materials: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized_assets = []

    for index, raw_material in enumerate(materials):
        asset_type = raw_material["asset_type"].strip().lower()
        rendering_mode = raw_material["rendering_mode"].strip().lower()
        position = raw_material["position"].strip().lower()
        title = _clean_optional_text(raw_material.get("title"))
        caption = _clean_optional_text(raw_material.get("caption"))
        alt_text = _clean_optional_text(raw_material.get("alt_text"))
        source_label = _clean_optional_text(raw_material.get("source_label"))
        content = _clean_optional_text(raw_material.get("content"))
        metadata = raw_material.get("data")

        if not isinstance(metadata, dict):
            metadata = {}

        if raw_material.get("image_generation_prompt"):
            metadata["image_generation_prompt"] = raw_material[
                "image_generation_prompt"
            ].strip()

        public_url = _clean_optional_text(raw_material.get("public_url"))
        mime_type = _clean_optional_text(raw_material.get("mime_type"))
        file_base64 = _clean_optional_text(raw_material.get("file_base64"))
        if public_url:
            metadata["image_source"] = "external_url"
        elif file_base64:
            metadata["image_source"] = "uploaded_file"
        elif raw_material.get("image_generation_prompt"):
            metadata["image_source"] = "generated_prompt"

        normalized_assets.append(
            {
                "asset_type": asset_type,
                "rendering_mode": rendering_mode,
                "position": position,
                "display_order": index,
                "title": title,
                "caption": caption,
                "alt_text": alt_text,
                "source_label": source_label,
                "content": content,
                "data": metadata or None,
                "public_url": public_url,
                "mime_type": mime_type,
                "file_base64": file_base64,
            }
        )

    return normalized_assets


def prepare_question_asset_record(
    material: dict[str, Any],
    *,
    storage_owner_id: uuid.UUID,
) -> dict[str, Any]:
    from src.models.models import QuestionAssets

    asset = QuestionAssets(
        asset_type=material["asset_type"],
        rendering_mode=material["rendering_mode"],
        position=material["position"],
        display_order=material["display_order"],
        title=material["title"],
        caption=material["caption"],
        alt_text=material["alt_text"],
        source_label=material["source_label"],
        content=material["content"],
        metadata_=material["data"],
        storage_status="not_required",
    )

    if (
        material["asset_type"] in VISUAL_ASSET_TYPES
        and material["rendering_mode"] == "generated_image"
    ):
        _attach_manual_visual_asset_storage(asset, material, storage_owner_id)

    return {
        "asset_type": asset.asset_type,
        "rendering_mode": asset.rendering_mode,
        "position": asset.position,
        "display_order": asset.display_order,
        "storage_status": asset.storage_status,
        "title": asset.title,
        "caption": asset.caption,
        "alt_text": asset.alt_text,
        "source_label": asset.source_label,
        "content": asset.content,
        "storage_provider": asset.storage_provider,
        "storage_key": asset.storage_key,
        "public_url": asset.public_url,
        "mime_type": asset.mime_type,
        "metadata_": asset.metadata_,
    }


async def get_question_assets_by_ids(
    *,
    asset_ids: list[uuid.UUID],
    db: AsyncSession,
) -> list["QuestionAssets"]:
    from src.models.models import QuestionAssets

    unique_asset_ids = list(dict.fromkeys(asset_ids))
    result = await db.execute(
        select(QuestionAssets).where(QuestionAssets.id.in_(unique_asset_ids))
    )
    assets = result.scalars().all()
    assets_by_id = {asset.id: asset for asset in assets}

    missing_asset_ids = [
        str(asset_id) for asset_id in unique_asset_ids if asset_id not in assets_by_id
    ]
    if missing_asset_ids:
        raise HTTPException(
            status_code=404,
            detail=(
                "Support materials not found for ids: "
                + ", ".join(missing_asset_ids)
            ),
        )

    return [assets_by_id[asset_id] for asset_id in unique_asset_ids]


def build_question_assets(
    storage_owner_id,
    question_assets: list[dict[str, Any]],
) -> list["QuestionAssets"]:
    from src.models.models import QuestionAssets

    assets: list[QuestionAssets] = []

    for material in question_assets:
        asset = QuestionAssets(
            **prepare_question_asset_record(
                material,
                storage_owner_id=storage_owner_id,
            )
        )
        assets.append(asset)

    return assets


def serialize_question_asset(asset: "QuestionAssets") -> dict[str, Any]:
    return {
        "id": asset.id,
        "asset_type": asset.asset_type,
        "rendering_mode": asset.rendering_mode,
        "position": asset.position,
        "display_order": asset.display_order,
        "storage_status": asset.storage_status,
        "title": asset.title,
        "caption": asset.caption,
        "alt_text": asset.alt_text,
        "source_label": asset.source_label,
        "content": asset.content,
        "storage_provider": asset.storage_provider,
        "storage_key": asset.storage_key,
        "public_url": asset.public_url,
        "mime_type": asset.mime_type,
        "data": asset.metadata_,
    }


def serialize_question_asset_for_prompt(asset: "QuestionAssets") -> dict[str, Any]:
    payload = {
        "id": str(asset.id),
        "asset_type": asset.asset_type,
        "rendering_mode": asset.rendering_mode,
        "position": asset.position,
        "display_order": asset.display_order,
        "title": asset.title,
        "caption": asset.caption,
        "alt_text": asset.alt_text,
        "source_label": asset.source_label,
        "content": asset.content,
        "public_url": asset.public_url,
        "mime_type": asset.mime_type,
        "data": asset.metadata_,
    }
    return {key: value for key, value in payload.items() if value is not None}


def _attach_visual_asset_storage(asset: "QuestionAssets", storage_owner_id) -> None:
    image_generation_prompt = None
    if isinstance(asset.metadata_, dict):
        image_generation_prompt = asset.metadata_.get("image_generation_prompt")

    if (
        not image_generation_prompt
        or not settings.QUESTION_ASSETS_ENABLE_IMAGE_GENERATION
    ):
        asset.storage_status = "pending_storage_configuration"
        return

    if not S3Storage.is_enabled():
        asset.storage_provider = "s3"
        asset.storage_status = "pending_storage_configuration"
        return

    try:
        image_bytes, mime_type, extension = _generate_image_bytes(
            prompt=image_generation_prompt,
        )
        upload_result = S3Storage.upload_question_asset(
            owner_id=storage_owner_id,
            extension=extension,
            body=image_bytes,
            content_type=mime_type,
        )
        asset.storage_provider = upload_result["storage_provider"]
        asset.storage_key = upload_result["storage_key"]
        asset.public_url = upload_result["public_url"]
        asset.mime_type = mime_type
        asset.storage_status = "stored"
    except Exception as exc:
        asset.storage_provider = "s3"
        asset.storage_status = "generation_failed"
        asset.metadata_ = {
            **(asset.metadata_ or {}),
            "storage_error": str(exc),
        }


def _attach_manual_visual_asset_storage(
    asset: "QuestionAssets",
    material: dict[str, Any],
    storage_owner_id,
) -> None:
    public_url = material.get("public_url")
    if public_url:
        asset.storage_provider = "external"
        asset.public_url = public_url
        asset.mime_type = material.get("mime_type")
        asset.storage_status = "stored"
        return

    file_base64 = material.get("file_base64")
    if file_base64:
        _attach_uploaded_visual_asset_storage(
            asset=asset,
            storage_owner_id=storage_owner_id,
            file_base64=file_base64,
            mime_type=material.get("mime_type"),
        )
        return

    _attach_visual_asset_storage(asset, storage_owner_id)


def _attach_uploaded_visual_asset_storage(
    *,
    asset: "QuestionAssets",
    storage_owner_id,
    file_base64: str,
    mime_type: str | None,
) -> None:
    if not S3Storage.is_enabled():
        raise ValueError("S3 is not fully configured for direct image uploads.")

    image_bytes, resolved_mime_type, extension = _decode_image_upload(
        file_base64=file_base64,
        mime_type=mime_type,
    )
    upload_result = S3Storage.upload_question_asset(
        owner_id=storage_owner_id,
        extension=extension,
        body=image_bytes,
        content_type=resolved_mime_type,
    )
    asset.storage_provider = upload_result["storage_provider"]
    asset.storage_key = upload_result["storage_key"]
    asset.public_url = upload_result["public_url"]
    asset.mime_type = resolved_mime_type
    asset.storage_status = "stored"


def _generate_image_bytes(*, prompt: str) -> tuple[bytes, str, str]:
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        response = client.images.generate(
            model=settings.OPENAI_IMAGE_MODEL,
            prompt=prompt,
            size=settings.OPENAI_IMAGE_SIZE,
            quality=settings.OPENAI_IMAGE_QUALITY,
        )
    except TypeError:
        response = client.images.generate(
            model=settings.OPENAI_IMAGE_MODEL,
            prompt=prompt,
            size=settings.OPENAI_IMAGE_SIZE,
        )

    image_base64 = getattr(response.data[0], "b64_json", None)
    if not image_base64:
        raise ValueError("Image generation did not return base64 data.")

    extension = settings.OPENAI_IMAGE_OUTPUT_FORMAT.lower()
    mime_type = f"image/{extension}"
    return base64.b64decode(image_base64), mime_type, extension


def generate_image_bytes_from_prompt(*, prompt: str) -> tuple[bytes, str, str]:
    return _generate_image_bytes(prompt=prompt)


def _decode_image_upload(
    *,
    file_base64: str,
    mime_type: str | None,
) -> tuple[bytes, str, str]:
    normalized_payload = file_base64.strip()
    detected_mime_type = _clean_optional_text(mime_type)

    data_url_match = DATA_URL_PATTERN.match(normalized_payload)
    if data_url_match:
        detected_mime_type = detected_mime_type or data_url_match.group("mime")
        normalized_payload = data_url_match.group("data")

    try:
        image_bytes = base64.b64decode(normalized_payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Invalid base64 payload for question asset.") from exc

    if not detected_mime_type or not detected_mime_type.startswith("image/"):
        raise ValueError(
            "Visual question assets uploaded by file must include a valid image mime_type."
        )

    extension = mimetypes.guess_extension(detected_mime_type) or ""
    extension = extension.lstrip(".")
    if not extension:
        raise ValueError(
            f"Unsupported mime_type for visual question asset: {detected_mime_type}."
        )

    return image_bytes, detected_mime_type, extension


def decode_uploaded_image(
    *,
    file_base64: str,
    mime_type: str | None,
) -> tuple[bytes, str, str]:
    return _decode_image_upload(file_base64=file_base64, mime_type=mime_type)


def _clean_optional_text(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    return text or None
