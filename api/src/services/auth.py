from __future__ import annotations


class AuthError(ValueError):
    pass


def get_claims(event: dict) -> dict[str, str]:
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )

    if not claims or "sub" not in claims:
        raise AuthError("Authenticated user claims are missing.")

    return claims


def get_user_sub(event: dict) -> str:
    return str(get_claims(event)["sub"])
