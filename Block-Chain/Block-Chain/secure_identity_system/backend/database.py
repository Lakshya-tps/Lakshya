import os
import pickle
import sqlite3
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_DIR = os.path.join(BASE_DIR, "..", "database")
RUNTIME_DB_DIR = os.getenv("SQLITE_DB_DIR") or (
    "/tmp/secure_identity_system" if os.getenv("VERCEL") else DEFAULT_DB_DIR
)
DB_PATH = os.path.join(RUNTIME_DB_DIR, "users.db")
ADMIN_DB_PATH = os.path.join(RUNTIME_DB_DIR, "admins.db")


def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def get_db_connection(role="user"):
    path = ADMIN_DB_PATH if role == "admin" else DB_PATH
    dir_path = os.path.dirname(os.path.abspath(path))
    os.makedirs(dir_path, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _get_column_names(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def _ensure_column(cursor, table_name, column_name, column_definition):
    if column_name not in _get_column_names(cursor, table_name):
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")


def init_db():
    for role in ["user", "admin"]:
        print(f"Initializing {role} database...")
        conn = get_db_connection(role)
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                encoding BLOB NOT NULL,
                identity_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_login_at TEXT,
                face_quality_score REAL NOT NULL DEFAULT 0,
                blockchain_status TEXT NOT NULL DEFAULT 'pending',
                tx_hash TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                event TEXT NOT NULL,
                success INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                details TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS identity_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                doc_code TEXT NOT NULL,
                doc_label TEXT NOT NULL DEFAULT '',
                doc_number TEXT NOT NULL,
                file_path TEXT,
                original_filename TEXT,
                mime_type TEXT,
                sha256 TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_identity_documents_unique
            ON identity_documents (user_email, doc_code, doc_label)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_identity_documents_user_email
            ON identity_documents (user_email)
            """
        )

        _ensure_column(cur, "users", "created_at", "TEXT")
        _ensure_column(cur, "users", "last_login_at", "TEXT")
        _ensure_column(cur, "users", "face_quality_score", "REAL NOT NULL DEFAULT 0")
        _ensure_column(cur, "users", "blockchain_status", "TEXT NOT NULL DEFAULT 'pending'")
        _ensure_column(cur, "users", "tx_hash", "TEXT")
        _ensure_column(cur, "users", "role", "TEXT NOT NULL DEFAULT 'user'")
        _ensure_column(cur, "users", "password_hash", "TEXT")
        _ensure_column(cur, "users", "is_verified", "INTEGER NOT NULL DEFAULT 1")
        _ensure_column(cur, "users", "approval_token", "TEXT")
        _ensure_column(cur, "logs", "details", "TEXT")

        now_value = utc_now_iso()
        cur.execute(
            """
            UPDATE users
            SET created_at = ?
            WHERE created_at IS NULL OR created_at = ''
            """,
            (now_value,),
        )
        cur.execute(
            """
            UPDATE users
            SET blockchain_status = 'pending'
            WHERE blockchain_status IS NULL OR blockchain_status = ''
            """
        )
        cur.execute(
            """
            UPDATE users
            SET face_quality_score = 0
            WHERE face_quality_score IS NULL
            """
        )

        conn.commit()
        conn.close()


def save_user(
    name,
    email,
    encoding,
    identity_hash,
    quality_score=0.0,
    blockchain_status="pending",
    tx_hash=None,
    role="user",
    password_hash=None,
    is_verified=1,
    approval_token=None,
):
    encoding_blob = pickle.dumps(encoding)
    created_at = utc_now_iso()
    conn = get_db_connection(role)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO users (
            name,
            email,
            encoding,
            identity_hash,
            created_at,
            face_quality_score,
            blockchain_status,
            tx_hash,
            role,
            password_hash,
            is_verified,
            approval_token
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            email,
            encoding_blob,
            identity_hash,
            created_at,
            float(quality_score),
            blockchain_status,
            tx_hash,
            role,
            password_hash,
            int(is_verified),
            approval_token,
        ),
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return user_id


def get_user_by_email(email, role="user"):
    conn = get_db_connection(role)
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    user = dict(row)
    try:
        user["encoding"] = pickle.loads(user["encoding"])
    except Exception:
        user["encoding"] = None
    return user


def get_user_by_approval_token(token):
    # Approval tokens are only for admins
    conn = get_db_connection("admin")
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE approval_token = ?", (token,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    user = dict(row)
    try:
        user["encoding"] = pickle.loads(user["encoding"])
    except Exception:
        user["encoding"] = None
    return user


def set_admin_verified(email):
    conn = get_db_connection("admin")
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_verified = 1, approval_token = NULL WHERE email = ?", (email,))
    conn.commit()
    conn.close()


def delete_user_by_email(email, role="user"):
    """Delete a user by email from the database.
    
    Returns:
        bool: True if a user was deleted, False otherwise.
    """
    conn = get_db_connection(role)
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE email = ?", (email,))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted




def get_all_encodings(role="user"):
    """Return all registered face encodings for duplicate-face detection.

    Returns:
        list of dicts with 'email' and 'encoding' keys.
    """
    conn = get_db_connection(role)
    cur = conn.cursor()
    cur.execute("SELECT email, encoding FROM users")
    rows = cur.fetchall()
    conn.close()

    results = []
    for row in rows:
        try:
            encoding = pickle.loads(row["encoding"])
            results.append({"email": row["email"], "encoding": encoding})
        except Exception:
            continue
    return results


def get_all_users(limit=50, role="user"):
    conn = get_db_connection(role)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            id,
            name,
            email,
            identity_hash,
            created_at,
            last_login_at,
            face_quality_score,
            blockchain_status,
            tx_hash,
            role,
            is_verified
        FROM users
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_user_login(email, role="user"):
    conn = get_db_connection(role)
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET last_login_at = ? WHERE email = ?",
        (utc_now_iso(), email),
    )
    conn.commit()
    conn.close()


def update_user_blockchain_status(email, status, tx_hash=None, role="user"):
    conn = get_db_connection(role)
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET blockchain_status = ?, tx_hash = COALESCE(?, tx_hash) WHERE email = ?",
        (status, tx_hash, email),
    )
    conn.commit()
    conn.close()


def log_event(email, event, success, details=None, role="user"):
    conn = get_db_connection(role)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO logs (email, event, success, timestamp, details)
        VALUES (?, ?, ?, ?, ?)
        """,
        (email, event, int(success), utc_now_iso(), details),
    )
    conn.commit()
    conn.close()


def get_logs(limit=80, role="user"):
    conn = get_db_connection(role)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, email, event, success, timestamp, details
        FROM logs
        ORDER BY datetime(timestamp) DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_metrics(role="user"):
    conn = get_db_connection(role)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM logs WHERE event = 'login'")
    login_attempts = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM logs WHERE event = 'login' AND success = 1")
    successful_logins = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM logs WHERE event = 'login' AND success = 0")
    failed_logins = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM users WHERE blockchain_status = 'synced'")
    synced_users = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(ROUND(AVG(face_quality_score), 1), 0) FROM users")
    average_quality = float(cur.fetchone()[0] or 0)

    conn.close()

    return {
        "total_users": total_users,
        "login_attempts": login_attempts,
        "successful_logins": successful_logins,
        "failed_logins": failed_logins,
        "synced_users": synced_users,
        "average_quality": average_quality,
    }


def clear_all_users(role="user"):
    """Delete all users from the database."""
    conn = get_db_connection(role)
    conn.execute("DELETE FROM users")
    conn.commit()
    conn.close()


def clear_all_logs(role="user"):
    """Delete all audit logs from the database."""
    conn = get_db_connection(role)
    conn.execute("DELETE FROM logs")
    conn.commit()
    conn.close()


def get_identity_document_by_key(user_email, doc_code, doc_label="", role="user"):
    normalized_label = doc_label or ""
    conn = get_db_connection(role)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM identity_documents
        WHERE user_email = ? AND doc_code = ? AND doc_label = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_email, doc_code, normalized_label),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_identity_document(
    user_email,
    doc_code,
    doc_label,
    doc_number,
    file_path=None,
    original_filename=None,
    mime_type=None,
    sha256=None,
    role="user",
):
    now_value = utc_now_iso()
    normalized_label = doc_label or ""
    conn = get_db_connection(role)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO identity_documents (
            user_email,
            doc_code,
            doc_label,
            doc_number,
            file_path,
            original_filename,
            mime_type,
            sha256,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_email, doc_code, doc_label)
        DO UPDATE SET
            doc_number = excluded.doc_number,
            file_path = excluded.file_path,
            original_filename = excluded.original_filename,
            mime_type = excluded.mime_type,
            sha256 = excluded.sha256,
            updated_at = excluded.updated_at
        """,
        (
            user_email,
            doc_code,
            normalized_label,
            doc_number,
            file_path,
            original_filename,
            mime_type,
            sha256,
            now_value,
            now_value,
        ),
    )
    conn.commit()
    conn.close()
    return get_identity_document_by_key(user_email, doc_code, normalized_label, role=role)


def list_identity_documents(user_email, role="user"):
    conn = get_db_connection(role)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM identity_documents
        WHERE user_email = ?
        ORDER BY datetime(updated_at) DESC, id DESC
        """,
        (user_email,),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_identity_document(doc_id, user_email, role="user"):
    conn = get_db_connection(role)
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM identity_documents WHERE id = ? AND user_email = ?",
        (int(doc_id), user_email),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def delete_identity_document(doc_id, user_email, role="user"):
    existing = get_identity_document(doc_id, user_email, role=role)
    if not existing:
        return None
    conn = get_db_connection(role)
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM identity_documents WHERE id = ? AND user_email = ?",
        (int(doc_id), user_email),
    )
    conn.commit()
    conn.close()
    return existing


def delete_identity_documents_for_user(user_email, role="user"):
    documents = list_identity_documents(user_email, role=role)
    conn = get_db_connection(role)
    cur = conn.cursor()
    cur.execute("DELETE FROM identity_documents WHERE user_email = ?", (user_email,))
    conn.commit()
    conn.close()
    return documents
