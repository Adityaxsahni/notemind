import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import audit
from app.config import get_settings
from app.deps import ACCESS_COOKIE, REFRESH_COOKIE, RedisDep, SessionDep
from app.mail import MailerDep, send_sign_in_code
from app.models import RefreshToken, User
from app.rate_limit import client_ip, enforce_rate_limit
from app.schemas import (
    FormTokenOut,
    LoginIn,
    OtpChallengeOut,
    OtpResendIn,
    OtpVerifyIn,
    SignupIn,
    UserOut,
)
from app.security import otp
from app.security.bot import issue_form_token, require_human
from app.security.passwords import DUMMY_HASH, hash_password, needs_rehash, verify_password
from app.security.tokens import (
    ACCESS_TOKEN_TTL,
    REFRESH_TOKEN_TTL,
    create_access_token,
    hash_token,
    new_opaque_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Refresh cookie is only sent to /auth/*, so it never travels with ordinary API calls.
_REFRESH_PATH = "/auth"
_INVALID_LOGIN = "Invalid email or password"
SIGNED_IN_COOKIE = "signed_in"


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    common = {"httponly": True, "secure": True, "samesite": "strict"}
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=int(ACCESS_TOKEN_TTL.total_seconds()),
        path="/",
        **common,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=int(REFRESH_TOKEN_TTL.total_seconds()),
        path=_REFRESH_PATH,
        **common,
    )
    # Not a credential: lets public pages show "Your courses" instead of "Log in" without an
    # API call. Readable by scripts on purpose; it carries no information beyond "1".
    response.set_cookie(
        SIGNED_IN_COOKIE,
        "1",
        max_age=int(REFRESH_TOKEN_TTL.total_seconds()),
        path="/",
        secure=True,
        samesite="strict",
    )


def clear_auth_cookies(response: Response) -> None:
    common = {"httponly": True, "secure": True, "samesite": "strict"}
    response.delete_cookie(ACCESS_COOKIE, path="/", **common)
    response.delete_cookie(REFRESH_COOKIE, path=_REFRESH_PATH, **common)
    response.delete_cookie(SIGNED_IN_COOKIE, path="/", secure=True, samesite="strict")


def _unauthorized() -> JSONResponse:
    response = JSONResponse({"detail": "Not authenticated"}, status_code=401)
    clear_auth_cookies(response)
    return response


def _start_session(
    session: Session, response: Response, user: User, family_id: uuid.UUID | None = None
) -> None:
    refresh_token = new_opaque_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            family_id=family_id or uuid.uuid4(),
            token_hash=hash_token(refresh_token),
            expires_at=datetime.now(UTC) + REFRESH_TOKEN_TTL,
        )
    )
    session.commit()
    set_auth_cookies(response, create_access_token(user.id), refresh_token)


def _revoke_family(session: Session, family_id: uuid.UUID) -> None:
    session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    session.commit()


def _password_accepted(
    session: Session, response: Response, user: User, redis, mailer
) -> User | OtpChallengeOut:
    """Step one done. With OTP on, email a code and wait for /otp/verify; else sign in."""
    settings = get_settings()
    if not settings.otp_required:
        _start_session(session, response, user)
        return user
    session.commit()  # the account (and any password rehash) is kept either way
    challenge = otp.start(redis, user.id)
    send_sign_in_code(mailer, user.email, challenge.code)
    response.status_code = status.HTTP_202_ACCEPTED
    return OtpChallengeOut(
        challenge_id=challenge.id,
        email_hint=otp.email_hint(user.email),
        expires_in=otp.CODE_TTL_SECONDS,
        dev_code=challenge.code if settings.show_otp_on_screen else None,
    )


@router.get("/form-token", response_model=FormTokenOut)
def form_token(response: Response) -> FormTokenOut:
    """A signed timestamp the sign-up and log-in forms send back (see app/security/bot.py)."""
    response.headers["Cache-Control"] = "no-store"
    return FormTokenOut(token=issue_form_token())


@router.post(
    "/signup", status_code=status.HTTP_201_CREATED, response_model=UserOut | OtpChallengeOut
)
def signup(
    body: SignupIn,
    request: Request,
    response: Response,
    session: SessionDep,
    redis: RedisDep,
    mailer: MailerDep,
) -> User | OtpChallengeOut:
    # Generous per-IP limit: a whole college hostel can share one public IP.
    enforce_rate_limit(redis, "signup", client_ip(request), limit=20, window_seconds=3600)
    require_human(
        form="signup",
        ip=client_ip(request),
        form_token=body.form_token,
        honeypot=body.website,
        captcha_token=body.captcha_token,
    )
    # TODO: answer an existing email with the same 202 "check your inbox" (and email the owner
    # instead), so sign-up can't be used to discover which addresses are registered.
    user = User(email=body.email.lower(), password_hash=hash_password(body.password))
    session.add(user)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from None
    # The code doubles as email verification: only the inbox's owner can finish signing up.
    return _password_accepted(session, response, user, redis, mailer)


@router.post("/login", response_model=UserOut | OtpChallengeOut)
def login(
    body: LoginIn,
    request: Request,
    response: Response,
    session: SessionDep,
    redis: RedisDep,
    mailer: MailerDep,
) -> User | OtpChallengeOut:
    email = body.email.lower()
    ip = client_ip(request)
    enforce_rate_limit(redis, "login", f"{ip}:{email}", limit=5, window_seconds=60)
    enforce_rate_limit(redis, "login-ip", ip, limit=50, window_seconds=60)
    require_human(
        form="login",
        ip=ip,
        form_token=body.form_token,
        honeypot=body.website,
        captcha_token=body.captcha_token,
    )

    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        verify_password(DUMMY_HASH, body.password)  # same timing as a real check
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_LOGIN)
    if not verify_password(user.password_hash, body.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_LOGIN)
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)

    return _password_accepted(session, response, user, redis, mailer)


@router.post("/otp/verify", response_model=UserOut)
def verify_otp(
    body: OtpVerifyIn, request: Request, response: Response, session: SessionDep, redis: RedisDep
) -> User:
    """Step two: the emailed code. Signs in on success."""
    enforce_rate_limit(redis, "otp-verify", client_ip(request), limit=30, window_seconds=600)
    user_id = otp.verify(redis, body.challenge_id, body.code)
    user = session.get(User, user_id)
    if user is None:  # deleted while the code was in flight
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_LOGIN)
    audit.record(session, "auth.signed_in", actor_id=user.id, request=request)
    _start_session(session, response, user)
    return user


@router.post("/otp/resend", response_model=OtpChallengeOut)
def resend_otp(
    body: OtpResendIn, request: Request, redis: RedisDep, session: SessionDep, mailer: MailerDep
) -> OtpChallengeOut:
    enforce_rate_limit(redis, "otp-resend", client_ip(request), limit=10, window_seconds=600)
    challenge = otp.resend(redis, body.challenge_id)
    user = session.get(User, challenge.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Start again.")
    send_sign_in_code(mailer, user.email, challenge.code)
    return OtpChallengeOut(
        challenge_id=challenge.id,
        email_hint=otp.email_hint(user.email),
        expires_in=otp.CODE_TTL_SECONDS,
        dev_code=challenge.code if get_settings().show_otp_on_screen else None,
    )


@router.post("/refresh", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def refresh(
    response: Response,
    session: SessionDep,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> JSONResponse | None:
    if not refresh_token:
        return _unauthorized()
    record = session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh_token))
    )
    now = datetime.now(UTC)
    if record is None or record.revoked_at is not None or record.expires_at <= now:
        return _unauthorized()
    if record.used_at is not None:
        # A rotated-out token came back: someone kept a copy. Kill every session in the family.
        _revoke_family(session, record.family_id)
        return _unauthorized()

    record.used_at = now
    user = session.get(User, record.user_id)
    if user is None:
        return _unauthorized()
    _start_session(session, response, user, family_id=record.family_id)
    return None


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    session: SessionDep,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> None:
    if refresh_token:
        record = session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh_token))
        )
        if record is not None:
            _revoke_family(session, record.family_id)
    clear_auth_cookies(response)
