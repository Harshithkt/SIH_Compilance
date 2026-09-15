"""Authentication and role-based access control."""

from app.config import settings

PASSWORD = settings.bootstrap_password


def _login(client, username: str, password: str = PASSWORD):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


class TestLogin:
    def test_bootstrap_accounts_can_sign_in(self, client):
        for username, role in (
            ("officer", "officer"),
            ("supervisor", "supervisor"),
            ("admin", "admin"),
        ):
            response = _login(client, username)
            assert response.status_code == 200, response.text
            assert response.json()["user"]["role"] == role

    def test_wrong_password_is_rejected(self, client):
        assert _login(client, "officer", "not-the-password").status_code == 401

    def test_unknown_account_is_rejected_the_same_way(self, client):
        unknown = _login(client, "nobody", "whatever")
        wrong = _login(client, "officer", "not-the-password")
        # The two must be indistinguishable, or the response enumerates usernames.
        assert unknown.status_code == wrong.status_code == 401
        assert unknown.json()["detail"] == wrong.json()["detail"]


class TestTokenRequired:
    def test_protected_endpoints_reject_anonymous_callers(self, client):
        for path in (
            "/api/v1/scans",
            "/api/v1/cases",
            "/api/v1/worklist",
            "/api/v1/stats",
            "/api/v1/ledger",
        ):
            assert client.get(path).status_code == 401, path

    def test_health_stays_public(self, client):
        assert client.get("/api/v1/system/health").status_code == 200

    def test_garbage_token_is_rejected(self, client):
        response = client.get("/api/v1/scans", headers={"Authorization": "Bearer not-a-jwt"})
        assert response.status_code == 401

    def test_valid_token_is_accepted(self, client, auth_headers):
        assert client.get("/api/v1/scans", headers=auth_headers()).status_code == 200

    def test_me_returns_the_signed_in_account(self, client, auth_headers):
        response = client.get("/api/v1/auth/me", headers=auth_headers("supervisor"))
        assert response.status_code == 200
        assert response.json()["username"] == "supervisor"


class TestRoles:
    def test_officer_cannot_manage_users(self, client, auth_headers):
        assert client.get("/api/v1/auth/users", headers=auth_headers("officer")).status_code == 403

    def test_admin_can_manage_users(self, client, auth_headers):
        response = client.get("/api/v1/auth/users", headers=auth_headers("admin"))
        assert response.status_code == 200
        assert {u["username"] for u in response.json()} == {"officer", "supervisor", "admin"}

    def test_officer_cannot_read_the_audit_log(self, client, auth_headers):
        assert client.get("/api/v1/auth/audit", headers=auth_headers("officer")).status_code == 403

    def test_supervisor_can_read_the_audit_log(self, client, auth_headers):
        response = client.get("/api/v1/auth/audit", headers=auth_headers("supervisor"))
        assert response.status_code == 200
        # Signing in to obtain the header above is itself an audited action.
        assert any(entry["action"] == "auth.login" for entry in response.json())

    def test_admin_inherits_the_lower_roles(self, client, auth_headers):
        assert client.get("/api/v1/auth/audit", headers=auth_headers("admin")).status_code == 200


class TestUserManagement:
    def test_admin_creates_an_account_that_can_then_sign_in(self, client, auth_headers):
        created = client.post(
            "/api/v1/auth/users",
            headers=auth_headers("admin"),
            json={
                "username": "Insp.Nair",
                "full_name": "Insp. M. Nair",
                "password": "field-work-2026",
                "role": "officer",
            },
        )
        assert created.status_code == 201, created.text
        assert created.json()["username"] == "insp.nair"  # normalised
        assert _login(client, "insp.nair", "field-work-2026").status_code == 200

    def test_duplicate_username_is_refused(self, client, auth_headers):
        response = client.post(
            "/api/v1/auth/users",
            headers=auth_headers("admin"),
            json={"username": "officer", "full_name": "Someone Else", "password": "another-one"},
        )
        assert response.status_code == 409

    def test_short_password_is_refused(self, client, auth_headers):
        response = client.post(
            "/api/v1/auth/users",
            headers=auth_headers("admin"),
            json={"username": "shorty", "full_name": "Short Password", "password": "abc"},
        )
        assert response.status_code == 422

    def test_officer_cannot_create_accounts(self, client, auth_headers):
        response = client.post(
            "/api/v1/auth/users",
            headers=auth_headers("officer"),
            json={"username": "sneaky", "full_name": "Self Promoted", "password": "long-enough"},
        )
        assert response.status_code == 403

    def test_deactivated_account_cannot_sign_in_or_use_a_live_token(self, client, auth_headers):
        headers = auth_headers("officer")
        assert client.get("/api/v1/scans", headers=headers).status_code == 200

        deactivated = client.post(
            "/api/v1/auth/users/officer/active?active=false", headers=auth_headers("admin")
        )
        assert deactivated.status_code == 200
        assert deactivated.json()["is_active"] is False

        # The token it already holds must stop working immediately, not at expiry.
        assert client.get("/api/v1/scans", headers=headers).status_code == 401
        assert _login(client, "officer").status_code == 401

    def test_admin_cannot_deactivate_themselves(self, client, auth_headers):
        response = client.post(
            "/api/v1/auth/users/admin/active?active=false", headers=auth_headers("admin")
        )
        assert response.status_code == 409


class TestPasswordChange:
    def test_officer_changes_their_own_password(self, client, auth_headers):
        response = client.post(
            "/api/v1/auth/password",
            headers=auth_headers("officer"),
            json={"current_password": PASSWORD, "new_password": "a-longer-secret"},
        )
        assert response.status_code == 200
        assert _login(client, "officer", "a-longer-secret").status_code == 200
        assert _login(client, "officer", PASSWORD).status_code == 401

    def test_wrong_current_password_is_refused(self, client, auth_headers):
        response = client.post(
            "/api/v1/auth/password",
            headers=auth_headers("officer"),
            json={"current_password": "wrong", "new_password": "a-longer-secret"},
        )
        assert response.status_code == 403


class TestIdentityIsNotTakenFromTheRequestBody:
    """The officer on a record is whoever signed in, not whoever the client names."""

    def test_review_records_the_authenticated_officer(self, client, auth_headers):
        scan_id = _record_scan(client, auth_headers)
        response = client.post(
            f"/api/v1/scans/{scan_id}/review",
            headers=auth_headers("officer"),
            # A client trying to sign another officer's name to this decision.
            json={"decision": "confirmed", "notes": "checked", "officer_name": "Someone Else"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["officer_decision_by"] == "Insp. R. Sharma"


class TestEscalatedCaseClosure:
    """A case whose response window lapsed is the supervisor's to close, and their
    name is what goes on the countersignature the docket prints."""

    def _escalated_case(self, client, auth_headers, db_session) -> str:
        scan_id = _record_scan(client, auth_headers)
        confirmed = client.post(
            f"/api/v1/scans/{scan_id}/review",
            headers=auth_headers("officer"),
            json={"decision": "confirmed", "notes": "finding stands"},
        )
        assert confirmed.status_code == 200, confirmed.text
        case = confirmed.json()["case"]
        assert case, "confirming a FIX/REVIEW finding should open a case"

        # Escalation normally happens once the due date passes; move the case there
        # directly rather than waiting out a 15-day window.
        from app.models import Case

        record = db_session.get(Case, case["id"])
        record.status = "escalated"
        db_session.commit()
        return case["id"]

    def test_officer_cannot_close_an_escalated_case(self, client, auth_headers, db_session):
        case_id = self._escalated_case(client, auth_headers, db_session)

        response = client.post(
            f"/api/v1/cases/{case_id}/close",
            headers=auth_headers("officer"),
            json={"resolution": "resolved", "notes": "corrected"},
        )
        assert response.status_code == 403

        still_open = client.get(f"/api/v1/cases/{case_id}", headers=auth_headers("officer"))
        assert still_open.json()["status"] == "escalated"

    def test_supervisor_closes_it_and_countersigns(self, client, auth_headers, db_session):
        case_id = self._escalated_case(client, auth_headers, db_session)

        response = client.post(
            f"/api/v1/cases/{case_id}/close",
            headers=auth_headers("supervisor"),
            json={"resolution": "resolved", "notes": "corrected on re-inspection"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "resolved"
        assert body["countersigned_by"] == settings.supervisor_role_name


def _record_scan(client, auth_headers) -> str:
    """Record one inspection from typed declarations.

    Deliberately uses the manual provider rather than a photograph: this test is about
    who gets named on the record, and routing it through a real OCR engine would make
    it fail for reasons — no Tesseract installed, no network — that have nothing to do
    with what it is checking.
    """
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (400, 200), color=(255, 255, 255)).save(buf, format="JPEG")
    response = client.post(
        "/api/v1/scans",
        headers=auth_headers("officer"),
        files={"image": ("label.jpg", buf.getvalue(), "image/jpeg")},
        data={
            "rule_version": "lmpc_2022_v2",
            "skip_quality_gate": "true",
            "provider": "manual",
            "raw_text": "Net Quantity: 200 g\nMRP: Rs. 45.00",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["scan"]["id"]
