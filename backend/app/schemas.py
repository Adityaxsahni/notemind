import re
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    model_validator,
)

from app.models import DocumentKind, DocumentStatus, Role
from app.security.passwords import password_problem

# Control characters (NUL, escape sequences, bidi overrides) have no place in names or
# questions and can hide text in logs and UIs. Newlines and tabs are allowed.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u202a-\u202e\u2066-\u2069]")


def _no_control_chars(value: str) -> str:
    if _CONTROL.search(value):
        raise ValueError("contains characters that aren't allowed")
    return value


class HumanCheckIn(BaseModel):
    """Bot checks for public forms (app/security/bot.py)."""

    form_token: str | None = Field(default=None, max_length=64)
    website: str = Field(default="", max_length=200)  # honeypot: hidden from people
    captcha_token: str | None = Field(default=None, max_length=4096)


class FormTokenOut(BaseModel):
    token: str


class SignupIn(HumanCheckIn):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)

    @model_validator(mode="after")
    def _strong_password(self) -> "SignupIn":
        problem = password_problem(self.password, str(self.email))
        if problem:
            raise ValueError(problem)
        return self


class LoginIn(HumanCheckIn):
    email: EmailStr
    # No minimum here: login must not reveal the password policy. Max bounds hashing cost.
    password: str = Field(max_length=128)


class PasswordConfirmIn(BaseModel):
    password: str = Field(max_length=128)


class OtpChallengeOut(BaseModel):
    """Password accepted; a code was emailed. Send it to /auth/otp/verify."""

    otp_required: bool = True
    challenge_id: str
    email_hint: str
    expires_in: int
    dev_code: str | None = None  # local development without SMTP only


class OtpVerifyIn(BaseModel):
    challenge_id: str = Field(min_length=10, max_length=64)
    code: str = Field(pattern=r"^\d{6}$")


class OtpResendIn(BaseModel):
    challenge_id: str = Field(min_length=10, max_length=64)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    created_at: datetime


CollectionName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
    AfterValidator(_no_control_chars),
]


class CollectionIn(BaseModel):
    name: CollectionName


class CollectionOut(BaseModel):
    id: uuid.UUID
    name: str
    role: Role
    created_at: datetime


class MemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    role: Role
    joined_at: datetime


class InviteCreateIn(BaseModel):
    expires_in_days: int = Field(default=7, ge=1, le=30)


class InviteCreatedOut(BaseModel):
    id: uuid.UUID
    token: str  # shown exactly once; only its hash is stored
    expires_at: datetime


class InviteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    expires_at: datetime
    created_at: datetime


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    kind: DocumentKind
    size_bytes: int
    status: DocumentStatus
    progress: int
    page_count: int | None
    transcribed_pages: int
    error: str | None
    created_at: datetime


class InviteAcceptIn(BaseModel):
    token: str = Field(min_length=1, max_length=128)


Question = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
    AfterValidator(_no_control_chars),
]


class SearchIn(BaseModel):
    query: Question


class SearchHit(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    page: int
    heading: str | None
    text: str
    score: float


class SearchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    low_confidence: bool
    chunks: list[SearchHit]


class AskIn(BaseModel):
    question: Question


Topic = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    AfterValidator(_no_control_chars),
]


class QuizIn(BaseModel):
    topic: Topic | None = None  # None: questions from across the whole collection
    num_questions: int = Field(default=5, ge=1, le=10)


class CitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    page: int
    heading: str | None


class QuizQuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    question: str
    options: list[str]
    answer: int
    explanation: str
    citation: CitationOut


class QuizOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    questions: list[QuizQuestionOut]
    found: bool
