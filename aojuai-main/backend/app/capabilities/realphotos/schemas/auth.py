from pydantic import BaseModel, ConfigDict, Field


class ChallengeCreate(BaseModel):
    client_key: str | None = Field(default=None, alias="clientKey", max_length=128)

    model_config = ConfigDict(populate_by_name=True)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)
    challenge_id: str = Field(..., alias="challengeId", min_length=1)
    challenge_code: str = Field(..., alias="challengeCode", min_length=1)

    model_config = ConfigDict(populate_by_name=True)


class RegisterRequest(BaseModel):
    """Merchant self-registration (FR-001 / architecture §9.2): captcha + create tenant."""

    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=8, max_length=50)
    nickname: str | None = Field(default=None, max_length=50)
    challenge_id: str = Field(..., alias="challengeId", min_length=1)
    challenge_code: str = Field(..., alias="challengeCode", min_length=1)

    model_config = ConfigDict(populate_by_name=True)
