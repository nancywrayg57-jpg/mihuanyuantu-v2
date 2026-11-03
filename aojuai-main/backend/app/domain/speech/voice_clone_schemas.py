"""Voice-clone-focused schema definitions for the speech domain."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SpeechVoiceCloneSupportView(BaseModel):
    enabled: bool = False
    provider_id: str | None = Field(None, alias="providerId")
    enrollment_model: str | None = Field(None, alias="enrollmentModel")
    synthesis_model: str | None = Field(None, alias="synthesisModel")
    max_upload_bytes: int = Field(..., alias="maxUploadBytes")
    max_duration_seconds: int = Field(..., alias="maxDurationSeconds")
    allowed_content_types: list[str] = Field(default_factory=list, alias="allowedContentTypes")
    note: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class SpeechVoiceCloneAssetView(BaseModel):
    id: int
    display_name: str = Field(alias="displayName")
    source_file_name: str = Field(alias="sourceFileName")
    source_content_type: str = Field(alias="sourceContentType")
    source_file_size_bytes: int = Field(alias="sourceFileSizeBytes")
    source_duration_ms: int = Field(alias="sourceDurationMs")
    transcript_text: str | None = Field(None, alias="transcriptText")
    language_type: str | None = Field(None, alias="languageType")
    status: str
    last_error: str | None = Field(None, alias="lastError")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime | None = Field(None, alias="updatedAt")
    created_by_user_id: int = Field(alias="createdByUserId")
    source_stream_url: str = Field(alias="sourceStreamUrl")

    model_config = ConfigDict(populate_by_name=True)


class SpeechVoiceCloneView(BaseModel):
    id: int
    asset_id: int = Field(alias="assetId")
    display_name: str = Field(alias="displayName")
    provider_id: str = Field(alias="providerId")
    enrollment_model: str = Field(alias="enrollmentModel")
    synthesis_model: str = Field(alias="synthesisModel")
    remote_voice_id: str = Field(alias="remoteVoiceId")
    language_type: str | None = Field(None, alias="languageType")
    status: str
    error_message: str | None = Field(None, alias="errorMessage")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime | None = Field(None, alias="updatedAt")
    created_by_user_id: int = Field(alias="createdByUserId")

    model_config = ConfigDict(populate_by_name=True)


class SpeechVoiceCloneWorkspaceItemView(BaseModel):
    asset: SpeechVoiceCloneAssetView
    clone: SpeechVoiceCloneView | None = None

    model_config = ConfigDict(populate_by_name=True)


class SpeechVoiceCloneWorkspacePayload(BaseModel):
    support: SpeechVoiceCloneSupportView
    items: list[SpeechVoiceCloneWorkspaceItemView] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class SpeechVoiceClonePreviewRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)

    model_config = ConfigDict(populate_by_name=True)
