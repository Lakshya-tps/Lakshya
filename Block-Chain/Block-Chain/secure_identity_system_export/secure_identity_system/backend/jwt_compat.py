import base64
import datetime
import hmac
import hashlib
import json


class ExpiredSignatureError(Exception):
    pass


class InvalidTokenError(Exception):
    pass


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _normalize_exp(payload: dict):
    exp = payload.get("exp")
    if exp is None:
        return
    if isinstance(exp, datetime.datetime):
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=datetime.timezone.utc)
        payload["exp"] = int(exp.timestamp())
        return
    if isinstance(exp, (int, float)):
        payload["exp"] = int(exp)
        return
    if isinstance(exp, str) and exp.isdigit():
        payload["exp"] = int(exp)
        return


def encode(payload: dict, secret: str, algorithm: str = "HS256") -> str:
    if algorithm != "HS256":
        raise ValueError("Only HS256 is supported by jwt_compat.")
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dict.")
    if not isinstance(secret, str) or not secret:
        raise ValueError("secret must be a non-empty string.")

    payload = dict(payload)
    _normalize_exp(payload)

    header = {"alg": "HS256", "typ": "JWT"}
    header_json = json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")

    header_b64 = _b64url_encode(header_json)
    payload_b64 = _b64url_encode(payload_json)
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(signature)
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def decode(token: str, secret: str, algorithms=None) -> dict:
    if not isinstance(token, str) or token.count(".") != 2:
        raise InvalidTokenError("Invalid token format.")
    if not isinstance(secret, str) or not secret:
        raise InvalidTokenError("Invalid secret.")
    if algorithms is not None and "HS256" not in algorithms:
        raise InvalidTokenError("Unsupported algorithm.")

    header_b64, payload_b64, sig_b64 = token.split(".")
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")

    try:
        header = json.loads(_b64url_decode(header_b64).decode("utf-8"))
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
        signature = _b64url_decode(sig_b64)
    except Exception as exc:
        raise InvalidTokenError("Invalid token encoding.") from exc

    if header.get("alg") != "HS256":
        raise InvalidTokenError("Unsupported token algorithm.")

    expected_sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected_sig):
        raise InvalidTokenError("Invalid token signature.")

    exp = payload.get("exp")
    if isinstance(exp, (int, float)):
        now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        if int(exp) < now:
            raise ExpiredSignatureError("Token has expired.")
    return payload

