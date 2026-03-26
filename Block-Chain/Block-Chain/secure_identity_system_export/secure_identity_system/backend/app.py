import os
import re
import datetime
import hashlib
import logging
import secrets
import hashlib
import importlib
import traceback
from functools import wraps
from pathlib import Path
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from dotenv import load_dotenv, set_key

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = (Path(BASE_DIR) / ".." / ".env").resolve()
load_dotenv(ENV_PATH)

_LAST_ENV_MTIME = None


def _reload_env_if_changed() -> None:
    global _LAST_ENV_MTIME
    try:
        mtime = ENV_PATH.stat().st_mtime
    except Exception:
        return
    if _LAST_ENV_MTIME is None or mtime != _LAST_ENV_MTIME:
        load_dotenv(ENV_PATH, override=True)
        _LAST_ENV_MTIME = mtime

try:
    jwt = importlib.import_module("jwt")
except ModuleNotFoundError:  # pragma: no cover
    import jwt_compat as jwt
from flask import Flask, jsonify, render_template, request, send_file
from flask_cors import CORS
from pydantic import ValidationError
from web3 import Web3
from werkzeug.exceptions import HTTPException

from blockchain import BlockchainClient
from database import (
    clear_all_logs,
    clear_all_users,
    delete_user_by_email,
    delete_identity_document,
    delete_identity_documents_for_user,
    get_all_encodings,
    get_all_users,
    get_db_connection,
    get_identity_document,
    get_identity_document_by_key,
    get_logs,
    get_metrics,
    get_user_by_email,
    get_user_by_approval_token,
    init_db,
    log_event,
    list_identity_documents,
    save_user,
    set_admin_verified,
    upsert_identity_document,
    update_user_blockchain_status,
    update_user_login,
)
import email_service
from email_service import send_registration_email_async, send_admin_approval_email_async
from face_auth import analyze_face, compare_face, decode_image, find_matching_face
from schemas import CapturePayload, LoginPayload, RegisterPayload, AdminRegisterPayload, AdminLoginPayload, validation_errors

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

UPLOAD_ROOT = (Path(BASE_DIR) / "uploads").resolve()
ALLOWED_DOC_CODES = {"aadhaar", "pan", "driving_license", "passport", "voter_id", "other"}
ALLOWED_UPLOAD_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf"}
DEFAULT_MAX_UPLOAD_MB = 10


def _parse_bool_query(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


def _hash_email_for_path(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def _ensure_upload_root():
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)


app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_MB", str(DEFAULT_MAX_UPLOAD_MB))) * 1024 * 1024


def _env_truthy(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "y", "on")


_db_initialized = False


def ensure_db_initialized():
    global _db_initialized
    if _db_initialized:
        return
    init_db()
    _db_initialized = True


# Ensure the DB schema exists even when running via the Flask CLI.
ensure_db_initialized()

blockchain = BlockchainClient()
JWT_SECRET_RAW = os.getenv("JWT_SECRET", "super-secure-jwt-key")


def _normalize_jwt_secret(raw: str) -> str:
    secret = str(raw or "")
    if len(secret.encode("utf-8")) >= 32:
        return secret
    # Derive a stable 32-byte+ secret to satisfy HS256 recommendations.
    derived = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    logging.getLogger(__name__).warning(
        "JWT_SECRET is shorter than 32 bytes; using a derived secret for HS256.",
    )
    return derived


JWT_SECRET = _normalize_jwt_secret(JWT_SECRET_RAW)


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return api_error("Missing or invalid authorization token.", status=401)
        
        token = auth_header.split(" ")[1]
        try:
            data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            current_user = get_user_by_email(data["email"], role="user")
            if not current_user:
                return api_error("User associated with token no longer exists.", status=401)
        except jwt.ExpiredSignatureError:
            return api_error("Session expired. Please log in again.", status=401)
        except jwt.InvalidTokenError:
            return api_error("Invalid token. Please log in again.", status=401)
            
        return f(current_user, *args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return api_error("Missing or invalid authorization token.", status=401)
        
        token = auth_header.split(" ")[1]
        try:
            data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            current_user = get_user_by_email(data["email"], role="admin")
            if not current_user:
                return api_error("User associated with token no longer exists.", status=401)
            if current_user.get("role") != "admin":
                return api_error("Administrator privileges required.", status=403)
        except jwt.ExpiredSignatureError:
            return api_error("Session expired. Please log in again.", status=401)
        except jwt.InvalidTokenError:
            return api_error("Invalid token. Please log in again.", status=401)
            
        return f(current_user, *args, **kwargs)
    return decorated


def api_success(message, status=200, **payload):
    def json_sanitize(value):
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return {str(key): json_sanitize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [json_sanitize(item) for item in value]
        if isinstance(value, (datetime.datetime, datetime.date)):
            return value.isoformat()
        if isinstance(value, (bytes, bytearray)):
            return value.decode("utf-8", errors="replace")

        value_type = type(value)
        if value_type.__module__ == "numpy":
            if hasattr(value, "item"):
                try:
                    return json_sanitize(value.item())
                except Exception:
                    pass
            if hasattr(value, "tolist"):
                try:
                    return json_sanitize(value.tolist())
                except Exception:
                    pass

        return str(value)

    body = {"ok": True, "message": message}
    body.update(payload)
    return jsonify(json_sanitize(body)), status


def api_error(message, status=400, **payload):
    def json_sanitize(value):
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return {str(key): json_sanitize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [json_sanitize(item) for item in value]
        if isinstance(value, (datetime.datetime, datetime.date)):
            return value.isoformat()
        if isinstance(value, (bytes, bytearray)):
            return value.decode("utf-8", errors="replace")

        value_type = type(value)
        if value_type.__module__ == "numpy":
            if hasattr(value, "item"):
                try:
                    return json_sanitize(value.item())
                except Exception:
                    pass
            if hasattr(value, "tolist"):
                try:
                    return json_sanitize(value.tolist())
                except Exception:
                    pass

        return str(value)

    body = {"ok": False, "message": message}
    body.update(payload)
    return jsonify(json_sanitize(body)), status


@app.errorhandler(Exception)
def handle_unexpected_error(exc):
    if request.path.startswith("/api/"):
        error_id = secrets.token_hex(6)
        log_path = (Path(BASE_DIR) / ".." / "server_api_errors.log").resolve()
        try:
            with open(log_path, "a", encoding="utf-8") as handle:
                handle.write("\n")
                timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
                handle.write(f"==== {timestamp} error_id={error_id} ====\n")
                handle.write(f"{request.method} {request.path}\n")
                handle.write(traceback.format_exc())
        except Exception:
            pass

        debug_enabled = _env_truthy("DEBUG", default=False)
        if isinstance(exc, HTTPException):
            return api_error(
                exc.description,
                status=getattr(exc, "code", 500),
                error_id=error_id,
            )
        if debug_enabled:
            return api_error(
                "Internal server error.",
                status=500,
                error_id=error_id,
                error_type=exc.__class__.__name__,
                error=str(exc),
            )
        return api_error("Internal server error.", status=500, error_id=error_id)
    if isinstance(exc, HTTPException):
        return exc
    raise exc


def parse_payload(model):
    raw_payload = request.get_json(silent=True) or {}
    try:
        return model.model_validate(raw_payload), None
    except ValidationError as exc:
        return None, api_error("Request validation failed.", status=400, errors=validation_errors(exc))


def build_identity_hash(name, email, encoding):
    payload = name.lower().encode() + b"|" + email.lower().encode() + b"|" + encoding.tobytes()
    return Web3.keccak(payload).hex()


def build_user_key(email):
    return Web3.keccak(text=email.lower()).hex()


def serialize_quality(analysis):
    def safe_float(value, default=0.0):
        try:
            return float(value)
        except Exception:
            return float(default)

    return {
        "score": safe_float(analysis.quality_score),
        "label": analysis.quality_label,
        "ready": analysis.ready,
        "issues": analysis.issues,
        "face_count": int(analysis.face_count or 0),
        "metrics": {
            "blur_score": safe_float(analysis.blur_score),
            "brightness": safe_float(analysis.brightness),
            "face_ratio": safe_float(analysis.face_ratio),
        },
    }


def _is_contract_deployed(chain_state: dict) -> bool:
    contract_address = chain_state.get("contract_address")
    if not chain_state.get("connected") or not contract_address:
        return False
    try:
        checksum_address = Web3.to_checksum_address(contract_address)
        code = blockchain.web3.eth.get_code(checksum_address)
        return bool(code) and len(code) > 0
    except Exception:
        return False


def current_blockchain_state():
    _reload_env_if_changed()
    state = blockchain.status()
    deployed = bool(state.get("deployed"))
    if not deployed and state.get("connected") and state.get("configured") and state.get("contract_address"):
        deployed = _is_contract_deployed(state)
        state["deployed"] = deployed
    write_ready = state.get("write_ready")
    ok = state.get("connected") and state.get("configured") and deployed and (write_ready is not False)
    state["state_label"] = "Active" if ok else "Not Connected"
    return state


def serialize_match(match_result):
    def safe_float(value, default=0.0):
        try:
            return float(value)
        except Exception:
            return float(default)

    return {
        "matched": bool(getattr(match_result, "match", False)),
        "distance": safe_float(getattr(match_result, "distance", 0.0)),
        "tolerance": safe_float(getattr(match_result, "tolerance", 0.0)),
        "confidence": safe_float(getattr(match_result, "confidence", 0.0)),
    }


def serialize_user(user):
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "identity_hash": user["identity_hash"],
        "created_at": user.get("created_at"),
        "last_login_at": user.get("last_login_at"),
        "face_quality_score": float(f"{float(user.get('face_quality_score') or 0):.1f}"),
        "blockchain_status": user.get("blockchain_status") or "pending",
        "tx_hash": user.get("tx_hash"),
    }


def serialize_log(log_row):
    return {
        "id": log_row["id"],
        "timestamp": log_row["timestamp"],
        "event": log_row["event"],
        "success": bool(log_row["success"]),
        "details": redact_log_details(log_row.get("details")),
    }


def redact_log_details(details):
    if not details:
        return details
    return re.sub(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        "[redacted]",
        details,
    )


def _is_zero_hash(value: str) -> bool:
    if not value:
        return True
    text = str(value).strip().lower()
    if text.startswith("0x"):
        text = text[2:]
    if not text:
        return True
    return set(text) == {"0"}


def _normalize_hash_hex(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if text.startswith("0x"):
        text = text[2:]
    return text or None


def determine_verification_state(chain_ready, chain_hash, stored_hash):
    if not chain_ready:
        return "offline"
    chain_norm = _normalize_hash_hex(chain_hash)
    stored_norm = _normalize_hash_hex(stored_hash)
    if chain_norm is None or _is_zero_hash(chain_norm):
        return "missing"
    if chain_norm == stored_norm:
        return "synced"
    return "mismatch"


@app.route("/api/health", methods=["GET"])
def health_check():
    return api_success(
        "Identity platform is healthy.",
        service="secure-identity-v2",
        metrics=get_metrics(),
        blockchain=current_blockchain_state(),
    )


@app.route("/api/overview", methods=["GET"])
def overview():
    metrics = get_metrics(role="user")
    login_attempts = metrics["login_attempts"]
    metrics["success_rate"] = round(
        (metrics["successful_logins"] / login_attempts) * 100, 1
    ) if login_attempts else 0.0
    return api_success(
        "Overview loaded.",
        metrics=metrics,
        users=[serialize_user(user) for user in get_all_users(limit=8, role="user")],
        logs=[serialize_log(log_row) for log_row in get_logs(limit=12, role="user")],
        blockchain=current_blockchain_state(),
    )


@app.route("/api/analyze-capture", methods=["POST"])
def analyze_capture():
    payload, error_response = parse_payload(CapturePayload)
    if error_response:
        return error_response
    assert payload is not None

    image_rgb = decode_image(payload.image)
    analysis = analyze_face(image_rgb)
    message = "Capture is ready." if analysis.ready else "Capture needs improvement."
    return api_success(message, quality=serialize_quality(analysis))


@app.route("/api/verify/<email>", methods=["GET"])
def verify_user(email):
    normalized_email = email.strip().lower()
    user = get_user_by_email(normalized_email)
    if not user:
        return api_error("User not found.", status=404)

    blockchain_state = current_blockchain_state()
    user_key = build_user_key(normalized_email)
    chain_hash = blockchain.get_identity(user_key) if blockchain_state["ready"] else None
    verification_state = determine_verification_state(
        blockchain_state["ready"],
        chain_hash,
        user["identity_hash"],
    )
    update_user_blockchain_status(normalized_email, verification_state)

    refreshed_user = get_user_by_email(normalized_email)
    return api_success(
        "Identity verification loaded.",
        user=serialize_user(refreshed_user),
        verification={
            "state": verification_state,
            "verified": verification_state == "synced",
            "chain_hash": chain_hash,
            "local_hash": user["identity_hash"],
        },
        blockchain=current_blockchain_state(),
    )


@app.route("/", methods=["GET"])
def home_page():
    return render_template("index.html")


@app.route("/register", methods=["GET"])
def register_page():
    return render_template("register.html")


@app.route("/login", methods=["GET"])
def login_page():
    return render_template("login.html")


@app.route("/admin/login", methods=["GET"])
def admin_login_page():
    return render_template("admin_login.html")


@app.route("/admin/register", methods=["GET"])
def admin_register_page():
    return render_template("admin_register.html")


@app.route("/profile", methods=["GET"])
def profile_page():
    return render_template("profile.html")


@app.route("/user", methods=["GET"])
@app.route("/user/dashboard", methods=["GET"])
def user_dashboard_page():
    return render_template("profile.html")


@app.route("/admin")
@app.route("/dashboard")
def dashboard_page():
    return render_template("admin.html")


@app.route("/api/register", methods=["POST"])
def register():
    payload, error_response = parse_payload(RegisterPayload)
    if error_response:
        return error_response
    assert payload is not None

    if get_user_by_email(payload.email, role="user"):
        log_event(payload.email, "register", False, "Duplicate email registration blocked.", role="user")
        return api_error("A user with that email already exists.", status=400)

    image_rgb = decode_image(payload.image)
    analysis = analyze_face(image_rgb)
    if analysis.encoding is None or not analysis.ready:
        log_event(payload.email, "register", False, "Capture quality below registration threshold.", role="user")
        return api_error(
            "Capture quality is not strong enough for registration.",
            status=400,
            quality=serialize_quality(analysis),
        )

    # --- Duplicate face prevention ---
    # Scan all existing face encodings to block the same person
    # from creating multiple accounts under different emails.
    all_encodings = get_all_encodings(role="user")
    dup_email, dup_distance = find_matching_face(analysis.encoding, all_encodings)
    if dup_email is not None:
        log_event(
            payload.email,
            "register",
            False,
            f"Duplicate face detected. Matches existing account (distance={dup_distance}).",
            role="user"
        )
        return api_error(
            "This face is already registered under a different account. "
            "Each person may only have one identity on the blockchain.",
            status=409,
        )

    identity_hash = build_identity_hash(payload.name, payload.email, analysis.encoding)
    user_key = build_user_key(payload.email)

    blockchain_state = current_blockchain_state()
    tx_hash = None
    blockchain_status = "offline"
    if blockchain_state["ready"]:
        tx_hash = blockchain.store_identity(user_key, identity_hash)
        blockchain_status = "synced" if tx_hash else "error"

    user_id = save_user(
        payload.name,
        payload.email,
        # Default user role
        encoding=analysis.encoding,
        identity_hash=identity_hash,
        quality_score=analysis.quality_score,
        blockchain_status=blockchain_status,
        tx_hash=tx_hash,
        role="user"
    )
    created_user = get_user_by_email(payload.email, role="user")

    detail_parts = [
        f"quality={analysis.quality_score}",
        f"chain={blockchain_status}",
    ]
    if tx_hash:
        detail_parts.append(f"tx={tx_hash}")
    log_event(payload.email, "register", True, "; ".join(detail_parts), role="user")

    # Send welcome email asynchronously
    send_registration_email_async(payload.email, payload.name)

    return api_success(
        "Identity registered successfully.",
        status=201,
        user={"id": user_id, **serialize_user(created_user)},
        quality=serialize_quality(analysis),
        blockchain={
            **current_blockchain_state(),
            "write_status": blockchain_status,
            "tx_hash": tx_hash,
        },
    )


@app.route("/api/login", methods=["POST"])
def login():
    payload, error_response = parse_payload(LoginPayload)
    if error_response:
        return error_response
    assert payload is not None

    user = get_user_by_email(payload.email, role="user")
    if not user:
        log_event(payload.email, "login", False, "User not found.", role="user")
        return api_error("User not found.", status=404)
    if user.get("encoding") is None:
        log_event(payload.email, "login", False, "Stored face encoding missing/corrupted.", role="user")
        return api_error(
            "Stored identity record is incomplete or corrupted. Please re-register this identity.",
            status=409,
        )

    image_rgb = decode_image(payload.image)
    analysis = analyze_face(image_rgb)
    if analysis.encoding is None or not analysis.ready:
        log_event(payload.email, "login", False, "Capture quality below authentication threshold.", role="user")
        return api_error(
            "Capture quality is not strong enough for authentication.",
            status=400,
            quality=serialize_quality(analysis),
        )

    match_result = compare_face(user["encoding"], analysis.encoding)
    if not match_result.match:
        log_event(
            payload.email,
            "login",
            False,
            f"Face mismatch. distance={match_result.distance}",
            role="user"
        )
        return api_error(
            "Face does not match the registered identity.",
            status=401,
            quality=serialize_quality(analysis),
            match=serialize_match(match_result),
        )

    blockchain_state = current_blockchain_state()
    user_key = build_user_key(payload.email)
    chain_hash = blockchain.get_identity(user_key) if blockchain_state["ready"] else None
    verification_state = determine_verification_state(
        blockchain_state["ready"],
        chain_hash,
        user["identity_hash"],
    )

    # If the chain is online but this user has no on-chain record (common after a redeploy),
    # optionally write the local hash to the chain so future logins are synced.
    if blockchain_state["ready"] and verification_state == "missing":
        auto_resync_missing = _parse_bool_query(os.getenv("AUTO_RESYNC_ON_MISMATCH"), default=True)
        if auto_resync_missing:
            tx_hash_missing = blockchain.store_identity(user_key, user["identity_hash"])
            if tx_hash_missing:
                chain_hash = blockchain.get_identity(user_key)
                verification_state = determine_verification_state(True, chain_hash, user["identity_hash"])
                update_user_blockchain_status(payload.email, verification_state, tx_hash=tx_hash_missing, role="user")
                log_event(payload.email, "blockchain_resync", True, f"tx={tx_hash_missing}", role="user")
            else:
                log_event(
                    payload.email,
                    "blockchain_resync",
                    False,
                    f"missing; error={getattr(blockchain, 'last_error', None)}",
                    role="user",
                )

    # ZERO-TRUST BLOCKCHAIN VERIFICATION
    # If the blockchain is online, but the hashes do not match, REJECT the login. 
    # This proves the local database identity was tampered with.
    if blockchain_state["ready"] and verification_state == "mismatch":
        auto_resync = _parse_bool_query(os.getenv("AUTO_RESYNC_ON_MISMATCH"), default=True)
        tx_hash = None
        if auto_resync:
            tx_hash = blockchain.store_identity(user_key, user["identity_hash"])
            if tx_hash:
                chain_hash = blockchain.get_identity(user_key)
                verification_state = determine_verification_state(True, chain_hash, user["identity_hash"])
                update_user_blockchain_status(payload.email, verification_state, tx_hash=tx_hash, role="user")
                log_event(
                    payload.email,
                    "blockchain_resync",
                    True,
                    f"tx={tx_hash}",
                    role="user",
                )

        if verification_state == "mismatch":
            log_event(
                payload.email,
                "login",
                False,
                "Zero-Trust Failure: Local identity hash does not match Blockchain.",
                role="user",
            )
            return api_error(
                "CRITICAL SECURITY ALERT: Your local identity record does not match the Blockchain record. Login prevented.",
                status=403,
                verification={
                    "state": verification_state,
                    "chain_hash": chain_hash,
                    "local_hash": user["identity_hash"],
                    "resync_attempted": bool(auto_resync),
                    "tx_hash": tx_hash,
                },
                blockchain_error=getattr(blockchain, "last_error", None),
            )

    update_user_login(payload.email, role="user")
    update_user_blockchain_status(payload.email, verification_state, role="user")
    refreshed_user = get_user_by_email(payload.email, role="user")

    log_event(
        payload.email,
        "login",
        True,
        f"distance={match_result.distance}; verification={verification_state}",
        role="user"
    )

    # ISSUE SESSION JWT
    token_payload = {
        "email": refreshed_user["email"],
        "name": refreshed_user["name"],
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)
    }
    jwt_token = jwt.encode(token_payload, JWT_SECRET, algorithm="HS256")

    return api_success(
        "Authentication successful.",
        authenticated=True,
        token=jwt_token,
        user=serialize_user(refreshed_user),
        quality=serialize_quality(analysis),
        match=serialize_match(match_result),
        verification={
            "state": verification_state,
            "verified": verification_state == "synced",
            "chain_hash": chain_hash,
            "local_hash": user["identity_hash"],
        },
        blockchain=current_blockchain_state(),
    )


@app.route("/api/admin/register", methods=["POST"])
def register_admin():
    payload, error_response = parse_payload(AdminRegisterPayload)
    if error_response:
        return error_response
    assert payload is not None

    if get_user_by_email(payload.email, role="admin"):
        log_event(payload.email, "admin_register", False, "Email already exists.", role="admin")
        return api_error("An account with this email already exists.", status=400)

    image_rgb = decode_image(payload.image)
    analysis = analyze_face(image_rgb)
    if analysis.encoding is None or not analysis.ready:
        log_event(payload.email, "admin_register", False, "Capture quality below required threshold.", role="admin")
        return api_error(
            "Capture quality is not strong enough for registration.",
            status=400,
            quality=serialize_quality(analysis),
        )

    all_encodings = get_all_encodings(role="admin")
    dup_email, _ = find_matching_face(analysis.encoding, all_encodings)
    if dup_email:
        log_event(payload.email, "admin_register", False, f"Face already registered to {dup_email}.", role="admin")
        return api_error("This face is already registered to an existing account.", status=400)

    pw_hash = generate_password_hash(payload.password)
    approval_token = secrets.token_urlsafe(32)
    identity_hash = build_identity_hash(payload.name, payload.email, analysis.encoding)

    user_id = save_user(
        name=payload.name,
        email=payload.email,
        encoding=analysis.encoding,
        identity_hash=identity_hash,
        quality_score=analysis.quality_score,
        role="admin",
        password_hash=pw_hash,
        is_verified=0,
        approval_token=approval_token,
    )

    send_admin_approval_email_async(payload.name, payload.email, approval_token)
    log_event(payload.email, "admin_register", True, "Admin registration pending approval.", role="admin")

    return api_success(
        "Registration received. An approval email has been sent to the Master Administrator.",
        quality=serialize_quality(analysis),
    )


@app.route("/api/admin/verify", methods=["GET"])
def verify_admin():
    token = request.args.get("token")
    if not token:
        return '<h1>Invalid Verification Link</h1><p>No token provided.</p>', 400

    user = get_user_by_approval_token(token)
    if not user:
        return '<h1>Verification Failed</h1><p>The approval link is invalid or has already been used.</p>', 400

    set_admin_verified(user["email"])
    
    blockchain_state = current_blockchain_state()
    if blockchain_state["ready"]:
        user_key = build_user_key(user["email"])
        tx_hash = blockchain.store_identity(user_key, user["identity_hash"])
        if tx_hash:
            update_user_blockchain_status(user["email"], "synced", tx_hash, role="admin")
        else:
            update_user_blockchain_status(user["email"], "error", role="admin")

    log_event(user["email"], "admin_verify", True, "Master Admin approved the registration.", role="admin")

    return f"""
    <html>
        <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
            <h1 style="color: #4CAF50;">Administrator Approved!</h1>
            <p>You have successfully approved <b>{user['email']}</b> for Admin privileges.</p>
            <p>They can now securely log in using 2-Factor Authentication.</p>
            <a href="/" style="display:inline-block; padding:10px 20px; margin-top: 20px; text-decoration:none; border-radius:5px;">Return to App</a>
        </body>
    </html>
    """


@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    payload, error_response = parse_payload(AdminLoginPayload)
    if error_response:
        return error_response
    assert payload is not None

    user = get_user_by_email(payload.email, role="admin")
    if not user or user.get("role") != "admin":
        log_event(payload.email, "admin_login", False, "Admin User not found or insufficient role.", role="admin")
        return api_error("Incorrect credentials or insufficient privileges.", status=401)
    if user.get("encoding") is None:
        log_event(payload.email, "admin_login", False, "Stored face encoding missing/corrupted.", role="admin")
        return api_error(
            "Stored identity record is incomplete or corrupted. Please re-register this identity.",
            status=409,
        )

    if not user.get("is_verified"):
        return api_error("This administrator account is pending approval from the Master Admin.", status=403)

    if not check_password_hash(user["password_hash"], payload.password):
        log_event(payload.email, "admin_login", False, "Incorrect password.", role="admin")
        return api_error("Incorrect credentials or insufficient privileges.", status=401)

    image_rgb = decode_image(payload.image)
    analysis = analyze_face(image_rgb)
    if analysis.encoding is None or not analysis.ready:
        log_event(payload.email, "admin_login", False, "Capture quality below authentication threshold.", role="admin")
        return api_error(
            "Capture quality is not strong enough for 2FA authentication.",
            status=400,
            quality=serialize_quality(analysis),
        )

    match_result = compare_face(user["encoding"], analysis.encoding)
    if not match_result.match:
        log_event(
            payload.email,
            "admin_login",
            False,
            f"Face mismatch. distance={match_result.distance}",
            role="admin"
        )
        return api_error(
            "Biometric verification failed. Face does not match the registered admin identity.",
            status=401,
            quality=serialize_quality(analysis),
            match=serialize_match(match_result),
        )

    blockchain_state = current_blockchain_state()
    user_key = build_user_key(payload.email)
    chain_hash = blockchain.get_identity(user_key) if blockchain_state["ready"] else None
    verification_state = determine_verification_state(
        blockchain_state["ready"],
        chain_hash,
        user["identity_hash"],
    )

    if blockchain_state["ready"] and verification_state == "missing":
        auto_resync_missing = _parse_bool_query(os.getenv("AUTO_RESYNC_ON_MISMATCH"), default=True)
        if auto_resync_missing:
            tx_hash_missing = blockchain.store_identity(user_key, user["identity_hash"])
            if tx_hash_missing:
                chain_hash = blockchain.get_identity(user_key)
                verification_state = determine_verification_state(True, chain_hash, user["identity_hash"])
                update_user_blockchain_status(payload.email, verification_state, tx_hash=tx_hash_missing, role="admin")
                log_event(payload.email, "blockchain_resync", True, f"tx={tx_hash_missing}", role="admin")
            else:
                log_event(
                    payload.email,
                    "blockchain_resync",
                    False,
                    f"missing; error={getattr(blockchain, 'last_error', None)}",
                    role="admin",
                )

    if blockchain_state["ready"] and verification_state == "mismatch":
        auto_resync = _parse_bool_query(os.getenv("AUTO_RESYNC_ON_MISMATCH"), default=True)
        tx_hash = None
        if auto_resync:
            tx_hash = blockchain.store_identity(user_key, user["identity_hash"])
            if tx_hash:
                chain_hash = blockchain.get_identity(user_key)
                verification_state = determine_verification_state(True, chain_hash, user["identity_hash"])
                update_user_blockchain_status(payload.email, verification_state, tx_hash=tx_hash, role="admin")
                log_event(
                    payload.email,
                    "blockchain_resync",
                    True,
                    f"tx={tx_hash}",
                    role="admin",
                )

        if verification_state == "mismatch":
            log_event(
                payload.email,
                "admin_login",
                False,
                "Zero-Trust Failure: Local identity hash does not match Blockchain.",
                role="admin",
            )
            return api_error(
                "CRITICAL SECURITY ALERT: Your local identity record does not match the Blockchain record. Login prevented.",
                status=403,
                blockchain_error=getattr(blockchain, "last_error", None),
            )

    update_user_login(payload.email, role="admin")
    update_user_blockchain_status(payload.email, verification_state, role="admin")
    refreshed_user = get_user_by_email(payload.email, role="admin")

    log_event(
        payload.email,
        "admin_login",
        True,
        f"distance={match_result.distance}; verification={verification_state}",
        role="admin"
    )

    token_payload = {
        "email": refreshed_user["email"],
        "name": refreshed_user["name"],
        "role": refreshed_user["role"],
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)
    }
    jwt_token = jwt.encode(token_payload, JWT_SECRET, algorithm="HS256")

    return api_success(
        "Administrator authentication successful.",
        authenticated=True,
        token=jwt_token,
        user=serialize_user(refreshed_user)
    )


@app.route("/api/profile", methods=["GET"])
@token_required
def profile_api(current_user):
    chain_state = current_blockchain_state()
    return api_success(
        "Profile loaded secure session.",
        user=serialize_user(current_user),
        blockchain_state=chain_state.get("state_label") or "Not Connected",
        blockchain_error=chain_state.get("last_error"),
        blockchain=chain_state,
    )


def _normalize_doc_code(value: str) -> str:
    code = (value or "").strip().lower()
    if code not in ALLOWED_DOC_CODES:
        raise ValueError("Unsupported document type.")
    return code


def _normalize_doc_label(doc_code: str, value: str) -> str:
    label = " ".join((value or "").split()).strip()
    if doc_code == "other":
        if len(label) < 2:
            raise ValueError("Document label is required for custom documents.")
        return label
    return ""


def _normalize_doc_number(doc_code: str, value: str) -> str:
    raw = " ".join((value or "").split()).strip()
    if not raw:
        raise ValueError("Document number is required.")

    if doc_code == "aadhaar":
        digits = re.sub(r"\D", "", raw)
        if len(digits) < 4:
            raise ValueError("Aadhaar number must contain at least 4 digits.")
        return digits

    normalized = raw.replace(" ", "").upper()
    if len(normalized) < 3:
        raise ValueError("Document number must be at least 3 characters.")
    return normalized


def _format_aadhaar_full(digits: str) -> str:
    digits_only = re.sub(r"\D", "", digits or "")
    if len(digits_only) == 12:
        return f"{digits_only[:4]}-{digits_only[4:8]}-{digits_only[8:]}"
    return digits_only


def _mask_doc_number(doc_code: str, normalized_number: str) -> str:
    if not normalized_number:
        return "--"

    if doc_code == "aadhaar":
        digits = re.sub(r"\D", "", normalized_number)
        last4 = digits[-4:] if len(digits) >= 4 else "XXXX"
        return f"XXXX-XXXX-{last4}"

    tail = normalized_number[-4:] if len(normalized_number) >= 4 else normalized_number
    return f"XXXX{tail}"


def _doc_display_label(doc_code: str, doc_label: str) -> str:
    mapping = {
        "aadhaar": "Aadhaar Card",
        "pan": "PAN Card",
        "driving_license": "Driving License",
        "passport": "Passport",
        "voter_id": "Voter ID",
    }
    if doc_code == "other":
        return doc_label or "Other Document"
    return mapping.get(doc_code, doc_code)


def _sort_identity_documents(documents):
    order = {"aadhaar": 0, "pan": 1, "driving_license": 2, "passport": 3, "voter_id": 4, "other": 5}
    return sorted(
        documents,
        key=lambda doc: (
            order.get(doc.get("doc_code") or "other", 99),
            (doc.get("doc_label") or "").lower(),
            int(doc.get("id") or 0),
        ),
    )


def serialize_identity_document(doc, reveal: bool = False):
    doc_code = doc.get("doc_code") or ""
    number = doc.get("doc_number") or ""
    masked = _mask_doc_number(doc_code, number)
    payload = {
        "id": doc.get("id"),
        "doc_code": doc_code,
        "doc_label": doc.get("doc_label") or "",
        "display_label": _doc_display_label(doc_code, doc.get("doc_label") or ""),
        "doc_number_masked": masked,
        "has_file": bool(doc.get("file_path")),
        "download_url": f"/api/identity-documents/{doc.get('id')}/download" if doc.get("file_path") else None,
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }
    if reveal:
        if doc_code == "aadhaar":
            payload["doc_number_full"] = _format_aadhaar_full(number)
        else:
            payload["doc_number_full"] = number
    return payload


def build_identity_scan_report(documents, reveal: bool) -> str:
    header = [
        "Face recognized successfully.",
        "",
        "Analyzing facial features...",
        "Match found in database.",
        "",
        "Scanning linked identity records...",
        "",
        "Display ALL available IDs clearly:",
        "",
    ]

    if not documents:
        return "\n".join(
            header
            + [
                "No identity records found for this individual.",
                "",
                "Users can upload additional identity documents to enhance verification.",
            ]
        )

    sorted_docs = _sort_identity_documents(documents)
    lines = header + ["The following IDs are associated with this person:"]
    for doc in sorted_docs:
        doc_code = doc.get("doc_code") or ""
        label = _doc_display_label(doc_code, doc.get("doc_label") or "")
        if reveal:
            if doc_code == "aadhaar":
                value = _format_aadhaar_full(doc.get("doc_number") or "")
            else:
                value = doc.get("doc_number") or "--"
        else:
            value = _mask_doc_number(doc_code, doc.get("doc_number") or "")
        lines.append(f"- {label}: {value}")

    required = {"aadhaar", "pan", "driving_license", "passport", "voter_id"}
    present = {doc.get("doc_code") for doc in documents if doc.get("doc_code")}
    if not required.issubset(present):
        lines.append("")
        lines.append("Some identity records were found. Additional documents can be uploaded.")

    lines.append("")
    lines.append("Users can upload additional identity documents to enhance verification.")
    return "\n".join(lines)


def _safe_upload_path(relative_path: str) -> Path:
    if not relative_path:
        raise FileNotFoundError("Missing file path.")

    abs_path = (Path(BASE_DIR) / relative_path).resolve()
    if UPLOAD_ROOT not in abs_path.parents and abs_path != UPLOAD_ROOT:
        raise FileNotFoundError("Invalid file path.")
    return abs_path


def _delete_uploaded_file(relative_path: str):
    if not relative_path:
        return
    try:
        abs_path = _safe_upload_path(relative_path)
    except FileNotFoundError:
        return
    try:
        abs_path.unlink(missing_ok=True)
    except Exception:
        return


def save_uploaded_doc_file(file_storage, user_email: str, doc_code: str, doc_label: str):
    _ensure_upload_root()
    original_filename = file_storage.filename or "document"
    cleaned_name = secure_filename(original_filename) or "document"
    ext = Path(cleaned_name).suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise ValueError("Unsupported file type. Upload PNG, JPG, JPEG, or PDF.")

    raw = file_storage.read()
    if not raw:
        raise ValueError("Uploaded file is empty.")

    sha256_hex = hashlib.sha256(raw).hexdigest()
    user_prefix = _hash_email_for_path(user_email)[:16]
    folder = (UPLOAD_ROOT / user_prefix)
    folder.mkdir(parents=True, exist_ok=True)

    label_part = doc_label if doc_code == "other" else doc_code
    label_part = secure_filename(label_part) or doc_code
    stored_filename = f"{doc_code}_{label_part}_{sha256_hex[:16]}{ext}"
    abs_path = (folder / stored_filename).resolve()

    with open(abs_path, "wb") as handle:
        handle.write(raw)

    relative_path = str(abs_path.relative_to(Path(BASE_DIR))).replace("\\", "/")
    mime_type = file_storage.mimetype or "application/octet-stream"
    return {
        "file_path": relative_path,
        "sha256": sha256_hex,
        "mime_type": mime_type,
        "original_filename": original_filename,
    }


@app.route("/api/identity-documents", methods=["GET"])
@token_required
def identity_documents_list(current_user):
    reveal = _parse_bool_query(request.args.get("reveal"), default=False)
    docs = list_identity_documents(current_user["email"], role="user")
    return api_success(
        "Identity documents loaded.",
        documents=[serialize_identity_document(doc, reveal=reveal) for doc in _sort_identity_documents(docs)],
        reveal=reveal,
    )


@app.route("/api/identity-documents", methods=["POST"])
@token_required
def identity_documents_upload(current_user):
    email = current_user["email"]
    try:
        doc_code = _normalize_doc_code(request.form.get("doc_code"))
        doc_label = _normalize_doc_label(doc_code, request.form.get("doc_label"))
        doc_number = _normalize_doc_number(doc_code, request.form.get("doc_number"))
    except ValueError as exc:
        return api_error(str(exc), status=400)

    existing = get_identity_document_by_key(email, doc_code, doc_label, role="user")

    uploaded = request.files.get("file")
    if not uploaded or not getattr(uploaded, "filename", ""):
        return api_error("Document file is required.", status=400)
    try:
        file_meta = save_uploaded_doc_file(uploaded, email, doc_code, doc_label)
    except ValueError as exc:
        return api_error(str(exc), status=400)

    file_path = file_meta["file_path"]
    original_filename = file_meta["original_filename"]
    mime_type = file_meta["mime_type"]
    sha256_value = file_meta["sha256"]

    stored = upsert_identity_document(
        user_email=email,
        doc_code=doc_code,
        doc_label=doc_label,
        doc_number=doc_number,
        file_path=file_path,
        original_filename=original_filename,
        mime_type=mime_type,
        sha256=sha256_value,
        role="user",
    )

    if existing and existing.get("file_path") and existing.get("file_path") != stored.get("file_path"):
        _delete_uploaded_file(existing.get("file_path"))

    docs = list_identity_documents(email, role="user")
    return api_success(
        "Identity document stored.",
        document=serialize_identity_document(stored, reveal=False),
        documents=[serialize_identity_document(doc, reveal=False) for doc in _sort_identity_documents(docs)],
    )


@app.route("/api/identity-documents/<int:doc_id>", methods=["DELETE"])
@token_required
def identity_documents_delete(current_user, doc_id):
    email = current_user["email"]
    deleted = delete_identity_document(doc_id, email, role="user")
    if not deleted:
        return api_error("Document not found.", status=404)
    _delete_uploaded_file(deleted.get("file_path"))
    docs = list_identity_documents(email, role="user")
    return api_success(
        "Identity document deleted.",
        documents=[serialize_identity_document(doc, reveal=False) for doc in _sort_identity_documents(docs)],
    )


@app.route("/api/identity-documents/<int:doc_id>/download", methods=["GET"])
@token_required
def identity_documents_download(current_user, doc_id):
    email = current_user["email"]
    doc = get_identity_document(doc_id, email, role="user")
    if not doc:
        return api_error("Document not found.", status=404)
    if not doc.get("file_path"):
        return api_error("No file is associated with this document.", status=404)

    try:
        abs_path = _safe_upload_path(doc["file_path"])
    except FileNotFoundError:
        return api_error("File is missing on disk.", status=404)

    if not abs_path.exists():
        return api_error("File is missing on disk.", status=404)

    return send_file(
        abs_path,
        as_attachment=True,
        download_name=doc.get("original_filename") or abs_path.name,
        mimetype=doc.get("mime_type") or "application/octet-stream",
    )


@app.route("/api/identity-scan", methods=["GET"])
@token_required
def identity_scan(current_user):
    reveal = _parse_bool_query(request.args.get("reveal"), default=False)
    docs = list_identity_documents(current_user["email"], role="user")
    report_text = build_identity_scan_report(docs, reveal=reveal)
    return api_success(
        "Identity scan complete.",
        reveal=reveal,
        report_text=report_text,
        documents=[serialize_identity_document(doc, reveal=reveal) for doc in _sort_identity_documents(docs)],
    )


@app.route("/api/users", methods=["GET"])
def users():
    return api_success("Users loaded.", users=[serialize_user(user) for user in get_all_users(role="user")])


@app.route("/api/logs", methods=["GET"])
def logs():
    return api_success("Audit log loaded.", logs=[serialize_log(log_row) for log_row in get_logs(role="user")])


@app.route("/api/users/<email>", methods=["DELETE"])
def delete_user(email):
    normalized_email = email.strip().lower()
    
    user = get_user_by_email(normalized_email, role="user")
    if not user:
        return api_error("User not found.", status=404)
        
    success = delete_user_by_email(normalized_email, role="user")
    if success:
        documents = delete_identity_documents_for_user(normalized_email, role="user")
        for doc in documents:
            _delete_uploaded_file(doc.get("file_path"))
        log_event(normalized_email, "delete", True, "Identity manually deleted from dashboard.", role="user")
        return api_success("User deleted successfully.")
    
    return api_error("Failed to delete user.", status=500)


@app.route("/api/admin/logs", methods=["DELETE"])
@admin_required
def clear_logs_endpoint(current_admin):
    clear_all_logs(role="admin")
    return api_success("All audit logs cleared.")


@app.route("/api/admin/users", methods=["DELETE"])
@admin_required
def clear_users_endpoint(current_admin):
    clear_all_users(role="admin")
    return api_success("All registered users cleared.")


@app.route("/api/admin/smtp", methods=["POST"])
@admin_required
def update_smtp_endpoint(current_admin):
    payload = request.get_json(silent=True) or {}
    email = payload.get("smtp_email")
    password = payload.get("smtp_password")
    
    if not email or not password:
        return api_error("Missing smtp_email or smtp_password.", status=400)
        
    set_key(ENV_PATH, "SMTP_USERNAME", email)
    set_key(ENV_PATH, "SMTP_PASSWORD", password)
    set_key(ENV_PATH, "SMTP_FROM_EMAIL", email)
    
    email_service.SMTP_USERNAME = email
    email_service.SMTP_PASSWORD = password
    email_service.SMTP_FROM_EMAIL = email
    
    return api_success("SMTP credentials successfully updated.")


@app.route("/api/admin/update_password", methods=["PUT"])
@admin_required
def update_password_endpoint(current_admin):
    payload = request.get_json(silent=True) or {}
    new_password = payload.get("new_password")
    
    if not new_password or len(new_password) < 6:
        return api_error("Password must be at least 6 characters.", status=400)
        
    pw_hash = generate_password_hash(new_password)
    
    conn = get_db_connection(role="admin")
    cur = conn.cursor()
    cur.execute("UPDATE users SET password_hash = ? WHERE email = ?", (pw_hash, current_admin["email"]))
    conn.commit()
    conn.close()
    
    log_event(current_admin["email"], "update_password", True, "Admin successfully changed their password.", role="admin")
    return api_success("Administrative password updated securely.")


@app.route("/api/admin/self", methods=["DELETE"])
@admin_required
def delete_self_endpoint(current_admin):
    deleted = delete_user_by_email(current_admin["email"], role="admin")
    if deleted:
        log_event(current_admin["email"], "delete_self", True, "Admin revoked their own identity and access.", role="admin")
        return api_success("Your administrative account has been securely erased.")
    return api_error("Failed to delete account.", status=500)


if __name__ == "__main__":
    ensure_db_initialized()
    with open("server_heartbeat.log", "w") as f:
        f.write(f"Server starting at {datetime.datetime.now()}\n")
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    debug = _env_truthy("DEBUG", default=False)
    app.run(host=host, port=port, debug=debug)
