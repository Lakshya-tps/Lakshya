import datetime
import io
import pathlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"

sys.path.insert(0, str(BACKEND_DIR))

import app as identity_app  # noqa: E402


class IdentityAppTestCase(unittest.TestCase):
    def setUp(self):
        self.client = identity_app.app.test_client()

    def auth_headers(self, email="ada@example.com"):
        token_payload = {
            "email": email,
            "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
        }
        token = identity_app.jwt.encode(token_payload, identity_app.JWT_SECRET, algorithm="HS256")
        if isinstance(token, bytes):
            token = token.decode("utf-8")
        return {"Authorization": f"Bearer {token}"}

    def quality(self, ready=True, score=82.5):
        return SimpleNamespace(
            encoding=np.array([0.1, 0.2, 0.3], dtype=np.float32),
            quality_score=score,
            quality_label="Excellent" if ready else "Needs review",
            blur_score=144.2,
            brightness=128.0,
            face_ratio=0.18,
            face_count=1,
            ready=ready,
            issues=[] if ready else ["Image is too soft."],
        )

    def match(self, matched=True):
        return SimpleNamespace(
            match=matched,
            distance=0.121 if matched else 0.622,
            tolerance=0.35,
            confidence=88.4 if matched else 22.8,
        )

    def test_pages_render(self):
        for route in ["/", "/register", "/login", "/dashboard"]:
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)

    @patch.object(identity_app, "current_blockchain_state")
    @patch.object(identity_app, "get_logs")
    @patch.object(identity_app, "get_all_users")
    @patch.object(identity_app, "get_metrics")
    def test_overview_returns_metrics(self, get_metrics, get_all_users, get_logs, current_blockchain_state):
        get_metrics.return_value = {
            "total_users": 3,
            "login_attempts": 4,
            "successful_logins": 3,
            "failed_logins": 1,
            "synced_users": 2,
            "average_quality": 74.1,
        }
        get_all_users.return_value = [
            {
                "id": 1,
                "name": "Ada Lovelace",
                "email": "ada@example.com",
                "identity_hash": "0x123",
                "created_at": "2026-03-11T12:00:00Z",
                "last_login_at": None,
                "face_quality_score": 74.1,
                "blockchain_status": "synced",
                "tx_hash": "0xtx",
            }
        ]
        get_logs.return_value = [
            {
                "id": 1,
                "email": "ada@example.com",
                "event": "login",
                "success": 1,
                "timestamp": "2026-03-11T12:00:00Z",
                "details": "distance=0.1",
            }
        ]
        current_blockchain_state.return_value = {
            "ready": False,
            "connected": False,
            "configured": False,
            "rpc_url": "http://127.0.0.1:7545",
            "contract_address": None,
            "account": None,
            "last_error": "Contract address not configured.",
        }

        response = self.client.get("/api/overview")
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["metrics"]["success_rate"], 75.0)
        self.assertEqual(len(payload["users"]), 1)
        self.assertEqual(len(payload["logs"]), 1)
        self.assertNotIn("email", payload["logs"][0])

    @patch.object(identity_app, "get_user_by_email")
    @patch.object(identity_app, "save_user")
    @patch.object(identity_app, "log_event")
    @patch.object(identity_app, "build_user_key")
    @patch.object(identity_app, "build_identity_hash")
    @patch.object(identity_app, "analyze_face")
    @patch.object(identity_app, "decode_image")
    @patch.object(identity_app, "current_blockchain_state")
    @patch.object(identity_app, "send_registration_email_async")
    def test_register_success_without_blockchain(
        self,
        send_registration_email_async,
        current_blockchain_state,
        decode_image,
        analyze_face,
        build_identity_hash,
        build_user_key,
        log_event,
        save_user,
        get_user_by_email,
    ):
        current_blockchain_state.return_value = {
            "ready": False,
            "connected": False,
            "configured": False,
            "rpc_url": "http://127.0.0.1:7545",
            "contract_address": None,
            "account": None,
            "last_error": "RPC connection unavailable.",
        }
        decode_image.return_value = object()
        analyze_face.return_value = self.quality(ready=True, score=84.7)
        build_identity_hash.return_value = "0xidentity"
        build_user_key.return_value = "0xuserkey"
        save_user.return_value = 9
        get_user_by_email.side_effect = [
            None,
            {
                "id": 9,
                "name": "Ada Lovelace",
                "email": "ada@example.com",
                "identity_hash": "0xidentity",
                "created_at": "2026-03-11T12:00:00Z",
                "last_login_at": None,
                "face_quality_score": 84.7,
                "blockchain_status": "offline",
                "tx_hash": None,
                "encoding": np.array([0.1, 0.2], dtype=np.float32),
            },
        ]

        response = self.client.post(
            "/api/register",
            json={
                "name": "Ada Lovelace",
                "email": "ada@example.com",
                "image": "data:image/jpeg;base64,test",
            },
        )
        payload = response.get_json()

        self.assertEqual(response.status_code, 201)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["user"]["email"], "ada@example.com")
        self.assertEqual(payload["blockchain"]["write_status"], "offline")
        log_event.assert_called()
        send_registration_email_async.assert_called_once_with("ada@example.com", "Ada Lovelace")

    def test_register_validation_error(self):
        response = self.client.post(
            "/api/register",
            json={"name": "A", "email": "bad-email", "image": ""},
        )
        payload = response.get_json()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(payload["ok"])
        self.assertGreaterEqual(len(payload["errors"]), 1)

    @patch.object(identity_app, "update_user_blockchain_status")
    @patch.object(identity_app, "update_user_login")
    @patch.object(identity_app, "log_event")
    @patch.object(identity_app, "build_user_key")
    @patch.object(identity_app, "compare_face")
    @patch.object(identity_app, "analyze_face")
    @patch.object(identity_app, "decode_image")
    @patch.object(identity_app, "current_blockchain_state")
    @patch.object(identity_app, "get_user_by_email")
    def test_login_success_without_blockchain(
        self,
        get_user_by_email,
        current_blockchain_state,
        decode_image,
        analyze_face,
        compare_face,
        build_user_key,
        log_event,
        update_user_login,
        update_user_blockchain_status,
    ):
        current_blockchain_state.return_value = {
            "ready": False,
            "connected": False,
            "configured": False,
            "rpc_url": "http://127.0.0.1:7545",
            "contract_address": None,
            "account": None,
            "last_error": "RPC connection unavailable.",
        }
        decode_image.return_value = object()
        analyze_face.return_value = self.quality(ready=True, score=79.3)
        compare_face.return_value = self.match(matched=True)
        build_user_key.return_value = "0xuserkey"
        get_user_by_email.side_effect = [
            {
                "id": 9,
                "name": "Ada Lovelace",
                "email": "ada@example.com",
                "identity_hash": "0xidentity",
                "created_at": "2026-03-11T12:00:00Z",
                "last_login_at": None,
                "face_quality_score": 84.7,
                "blockchain_status": "offline",
                "tx_hash": None,
                "encoding": np.array([0.1, 0.2], dtype=np.float32),
            },
            {
                "id": 9,
                "name": "Ada Lovelace",
                "email": "ada@example.com",
                "identity_hash": "0xidentity",
                "created_at": "2026-03-11T12:00:00Z",
                "last_login_at": "2026-03-11T13:00:00Z",
                "face_quality_score": 84.7,
                "blockchain_status": "offline",
                "tx_hash": None,
                "encoding": np.array([0.1, 0.2], dtype=np.float32),
            },
        ]

        response = self.client.post(
            "/api/login",
            json={
                "email": "ada@example.com",
                "image": "data:image/jpeg;base64,test",
            },
        )
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["authenticated"])
        self.assertEqual(payload["verification"]["state"], "offline")
        update_user_login.assert_called_once_with("ada@example.com")
        update_user_blockchain_status.assert_called_once_with("ada@example.com", "offline")
        log_event.assert_called()

    @patch.object(identity_app, "log_event")
    @patch.object(identity_app, "compare_face")
    @patch.object(identity_app, "analyze_face")
    @patch.object(identity_app, "decode_image")
    @patch.object(identity_app, "get_user_by_email")
    def test_login_face_mismatch(
        self,
        get_user_by_email,
        decode_image,
        analyze_face,
        compare_face,
        log_event,
    ):
        get_user_by_email.return_value = {
            "id": 9,
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "identity_hash": "0xidentity",
            "created_at": "2026-03-11T12:00:00Z",
            "last_login_at": None,
            "face_quality_score": 84.7,
            "blockchain_status": "offline",
            "tx_hash": None,
            "encoding": np.array([0.1, 0.2], dtype=np.float32),
        }
        decode_image.return_value = object()
        analyze_face.return_value = self.quality(ready=True, score=76.0)
        compare_face.return_value = self.match(matched=False)

        response = self.client.post(
            "/api/login",
            json={
                "email": "ada@example.com",
                "image": "data:image/jpeg;base64,test",
            },
        )
        payload = response.get_json()

        self.assertEqual(response.status_code, 401)
        self.assertFalse(payload["ok"])
        self.assertIn("match", payload)
        log_event.assert_called_once()

    @patch.object(identity_app, "log_event")
    @patch.object(identity_app, "find_matching_face")
    @patch.object(identity_app, "get_all_encodings")
    @patch.object(identity_app, "analyze_face")
    @patch.object(identity_app, "decode_image")
    @patch.object(identity_app, "get_user_by_email")
    def test_register_duplicate_face_blocked(
        self,
        get_user_by_email,
        decode_image,
        analyze_face,
        get_all_encodings,
        find_matching_face,
        log_event,
    ):
        """Registration must fail if the same face is already registered under another email."""
        get_user_by_email.return_value = None  # email is new
        decode_image.return_value = object()
        analyze_face.return_value = self.quality(ready=True, score=82.0)
        get_all_encodings.return_value = [
            {"email": "existing@example.com", "encoding": np.array([0.1, 0.2, 0.3], dtype=np.float32)},
        ]
        find_matching_face.return_value = ("existing@example.com", 0.22)

        response = self.client.post(
            "/api/register",
            json={
                "name": "Ada Lovelace",
                "email": "new_ada@example.com",
                "image": "data:image/jpeg;base64,test",
            },
        )
        payload = response.get_json()

        self.assertEqual(response.status_code, 409)
        self.assertFalse(payload["ok"])
        self.assertIn("already registered", payload["message"])
        log_event.assert_called_once()

    @patch.object(identity_app, "update_user_blockchain_status")
    @patch.object(identity_app, "update_user_login")
    @patch.object(identity_app, "log_event")
    @patch.object(identity_app, "build_user_key")
    @patch.object(identity_app, "compare_face")
    @patch.object(identity_app, "analyze_face")
    @patch.object(identity_app, "decode_image")
    @patch.object(identity_app, "current_blockchain_state")
    @patch.object(identity_app, "get_user_by_email")
    def test_login_relaxed_tolerance_allows_same_user(
        self,
        get_user_by_email,
        current_blockchain_state,
        decode_image,
        analyze_face,
        compare_face,
        build_user_key,
        log_event,
        update_user_login,
        update_user_blockchain_status,
    ):
        """Login should succeed even when histogram distance is ~0.5 (within new 0.60 tolerance)."""
        current_blockchain_state.return_value = {
            "ready": False,
            "connected": False,
            "configured": False,
            "rpc_url": "http://127.0.0.1:7545",
            "contract_address": None,
            "account": None,
            "last_error": "RPC connection unavailable.",
        }
        decode_image.return_value = object()
        analyze_face.return_value = self.quality(ready=True, score=72.0)
        # Distance of 0.5 would FAIL with old tolerance (0.35), but PASSES with new (0.60)
        compare_face.return_value = SimpleNamespace(
            match=True, distance=0.50, tolerance=0.60, confidence=50.0
        )
        build_user_key.return_value = "0xuserkey"
        get_user_by_email.side_effect = [
            {
                "id": 12,
                "name": "Ada Lovelace",
                "email": "ada@example.com",
                "identity_hash": "0xidentity",
                "created_at": "2026-03-11T12:00:00Z",
                "last_login_at": None,
                "face_quality_score": 80.0,
                "blockchain_status": "offline",
                "tx_hash": None,
                "encoding": np.array([0.1, 0.2], dtype=np.float32),
            },
            {
                "id": 12,
                "name": "Ada Lovelace",
                "email": "ada@example.com",
                "identity_hash": "0xidentity",
                "created_at": "2026-03-11T12:00:00Z",
                "last_login_at": "2026-03-11T13:00:00Z",
                "face_quality_score": 80.0,
                "blockchain_status": "offline",
                "tx_hash": None,
                "encoding": np.array([0.1, 0.2], dtype=np.float32),
            },
        ]

        response = self.client.post(
            "/api/login",
            json={
                "email": "ada@example.com",
                "image": "data:image/jpeg;base64,test",
            },
        )
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["authenticated"])
        update_user_login.assert_called_once_with("ada@example.com")


    @patch.object(identity_app, "delete_user_by_email")
    @patch.object(identity_app, "_delete_uploaded_file")
    @patch.object(identity_app, "delete_identity_documents_for_user")
    @patch.object(identity_app, "log_event")
    @patch.object(identity_app, "get_user_by_email")
    def test_delete_user(
        self,
        get_user_by_email,
        log_event,
        delete_identity_documents_for_user,
        _delete_uploaded_file,
        delete_user_by_email,
    ):
        """Delete user endpoint should remove the user and return success."""
        get_user_by_email.return_value = {
            "id": 1,
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "identity_hash": "0x123",
        }
        delete_user_by_email.return_value = True
        delete_identity_documents_for_user.return_value = [
            {
                "id": 1,
                "user_email": "ada@example.com",
                "doc_code": "pan",
                "doc_label": "",
                "doc_number": "ABCDE1234F",
                "file_path": "uploads/u/doc.pdf",
            }
        ]
        
        response = self.client.delete("/api/users/ada@example.com")
        payload = response.get_json()
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["ok"])
        delete_user_by_email.assert_called_once_with("ada@example.com", role="user")
        delete_identity_documents_for_user.assert_called_once_with("ada@example.com", role="user")
        _delete_uploaded_file.assert_called_once()
        log_event.assert_called_once()


    @patch.object(identity_app, "list_identity_documents")
    @patch.object(identity_app, "get_user_by_email")
    def test_identity_scan_no_docs(self, get_user_by_email, list_identity_documents):
        get_user_by_email.return_value = {
            "id": 1,
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "identity_hash": "0x1",
            "encoding": np.array([0.1], dtype=np.float32),
        }
        list_identity_documents.return_value = []

        response = self.client.get("/api/identity-scan?reveal=0", headers=self.auth_headers())
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["ok"])
        self.assertIn("No identity records found for this individual.", payload["report_text"])
        self.assertIn("Users can upload additional identity documents", payload["report_text"])


    @patch.object(identity_app, "list_identity_documents")
    @patch.object(identity_app, "get_user_by_email")
    def test_identity_scan_partial_docs_message(self, get_user_by_email, list_identity_documents):
        get_user_by_email.return_value = {
            "id": 1,
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "identity_hash": "0x1",
            "encoding": np.array([0.1], dtype=np.float32),
        }
        list_identity_documents.return_value = [
            {
                "id": 1,
                "user_email": "ada@example.com",
                "doc_code": "pan",
                "doc_label": "",
                "doc_number": "ABCDE1234F",
                "file_path": None,
                "original_filename": None,
                "mime_type": None,
                "sha256": None,
                "created_at": "2026-03-11T12:00:00Z",
                "updated_at": "2026-03-11T12:00:00Z",
            }
        ]

        response = self.client.get("/api/identity-scan?reveal=0", headers=self.auth_headers())
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["ok"])
        self.assertIn("Some identity records were found. Additional documents can be uploaded.", payload["report_text"])
        self.assertIn("- PAN Card:", payload["report_text"])


    @patch.object(identity_app, "list_identity_documents")
    @patch.object(identity_app, "get_user_by_email")
    def test_identity_documents_reveal_toggle(self, get_user_by_email, list_identity_documents):
        get_user_by_email.return_value = {
            "id": 1,
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "identity_hash": "0x1",
            "encoding": np.array([0.1], dtype=np.float32),
        }
        list_identity_documents.return_value = [
            {
                "id": 1,
                "user_email": "ada@example.com",
                "doc_code": "aadhaar",
                "doc_label": "",
                "doc_number": "123456789012",
                "file_path": None,
                "original_filename": None,
                "mime_type": None,
                "sha256": None,
                "created_at": "2026-03-11T12:00:00Z",
                "updated_at": "2026-03-11T12:00:00Z",
            }
        ]

        masked = self.client.get("/api/identity-documents?reveal=0", headers=self.auth_headers()).get_json()
        revealed = self.client.get("/api/identity-documents?reveal=1", headers=self.auth_headers()).get_json()

        self.assertTrue(masked["ok"])
        self.assertTrue(revealed["ok"])
        self.assertIn("doc_number_masked", masked["documents"][0])
        self.assertNotIn("doc_number_full", masked["documents"][0])
        self.assertEqual(revealed["documents"][0]["doc_number_full"], "1234-5678-9012")


    @patch.object(identity_app, "save_uploaded_doc_file")
    @patch.object(identity_app, "list_identity_documents")
    @patch.object(identity_app, "upsert_identity_document")
    @patch.object(identity_app, "get_identity_document_by_key")
    @patch.object(identity_app, "get_user_by_email")
    def test_identity_documents_upload_upsert(
        self,
        get_user_by_email,
        get_identity_document_by_key,
        upsert_identity_document,
        list_identity_documents,
        save_uploaded_doc_file,
    ):
        get_user_by_email.return_value = {
            "id": 1,
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "identity_hash": "0x1",
            "encoding": np.array([0.1], dtype=np.float32),
        }
        get_identity_document_by_key.return_value = None
        save_uploaded_doc_file.return_value = {
            "file_path": "uploads/u/passport.pdf",
            "sha256": "abc",
            "mime_type": "application/pdf",
            "original_filename": "passport.pdf",
        }

        stored_doc = {
            "id": 99,
            "user_email": "ada@example.com",
            "doc_code": "passport",
            "doc_label": "",
            "doc_number": "P1234567",
            "file_path": "uploads/u/passport.pdf",
            "original_filename": "passport.pdf",
            "mime_type": "application/pdf",
            "sha256": "abc",
            "created_at": "2026-03-11T12:00:00Z",
            "updated_at": "2026-03-11T12:00:00Z",
        }
        upsert_identity_document.return_value = stored_doc
        list_identity_documents.return_value = [stored_doc]

        response = self.client.post(
            "/api/identity-documents",
            data={
                "doc_code": "passport",
                "doc_number": "P1234567",
                "file": (io.BytesIO(b"%PDF test"), "passport.pdf"),
            },
            headers=self.auth_headers(),
            content_type="multipart/form-data",
        )
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["ok"])
        upsert_identity_document.assert_called_once()

    @patch.object(identity_app, "get_user_by_email")
    def test_identity_documents_upload_requires_file(self, get_user_by_email):
        get_user_by_email.return_value = {
            "id": 1,
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "identity_hash": "0x1",
            "encoding": np.array([0.1], dtype=np.float32),
        }

        response = self.client.post(
            "/api/identity-documents",
            data={"doc_code": "pan", "doc_number": "ABCDE1234F"},
            headers=self.auth_headers(),
        )
        payload = response.get_json()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(payload["ok"])
        self.assertIn("Document file is required", payload["message"])

if __name__ == "__main__":
    unittest.main()
