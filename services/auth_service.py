import hashlib
import hmac
import secrets

from database import get_connection


def hash_password(password: str) -> str:
    password = (password or "").strip()
    if not password:
        return ""

    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
    return f"pbkdf2$sha256${salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    if not password or not stored_hash:
        return False

    password = password.strip()
    if stored_hash.startswith("pbkdf2$"):
        try:
            _, algorithm, salt, expected = stored_hash.split("$", 3)
            if algorithm != "sha256":
                return False
            derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
            return hmac.compare_digest(derived.hex(), expected)
        except ValueError:
            return False

    legacy_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy_hash, stored_hash)


def _hash_password(password: str) -> str:
    return hash_password(password)


def prepare_session_for_user(session_state):
    session_state["active_page"] = "🏠 Dashboard"
    session_state["nav_target"] = None
    session_state["app_mode"] = "dashboard"
    return session_state


def reset_session_for_logout(session_state):
    session_state["user"] = None
    session_state["tenant"] = None
    session_state["active_page"] = "🏠 Dashboard"
    session_state["nav_target"] = None
    session_state["app_mode"] = "auth"
    return session_state


def create_tenant(name: str, slug: str | None = None, plan: str = "starter"):
    connection = get_connection()
    cursor = connection.cursor()
    tenant_slug = (slug or name.lower().replace(" ", "-")).strip()

    cursor.execute(
        "INSERT INTO tenants (name, slug, plan, is_active) VALUES (?, ?, ?, 1)",
        (name.strip(), tenant_slug, plan),
    )
    tenant_id = cursor.lastrowid
    connection.commit()
    connection.close()
    return {"id": tenant_id, "name": name.strip(), "slug": tenant_slug, "plan": plan}


def create_tenant_user(name: str, email: str, password: str, tenant_name: str, role: str = "owner"):
    email = (email or "").strip().lower()
    name = (name or "").strip()
    password = (password or "").strip()

    if not name or not email or not password or not tenant_name:
        return {"success": False, "message": "All fields are required."}

    connection = get_connection()
    cursor = connection.cursor()

    existing = cursor.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        connection.close()
        return {"success": False, "message": "An account with that email already exists."}

    tenant = cursor.execute(
        "SELECT id FROM tenants WHERE LOWER(name) = LOWER(?) OR LOWER(slug) = LOWER(?)",
        (tenant_name, tenant_name.lower().replace(" ", "-")),
    ).fetchone()

    if tenant:
        tenant_id = tenant[0]
    else:
        tenant_slug = tenant_name.strip().lower().replace(" ", "-")
        cursor.execute(
            "INSERT INTO tenants (name, slug, plan, is_active) VALUES (?, ?, 'starter', 1)",
            (tenant_name.strip(), tenant_slug),
        )
        tenant_id = cursor.lastrowid

    password_hash = _hash_password(password)
    cursor.execute(
        "INSERT INTO users (tenant_id, name, email, password_hash, role, is_active) VALUES (?, ?, ?, ?, ?, 1)",
        (tenant_id, name, email, password_hash, role),
    )
    user_id = cursor.lastrowid
    connection.commit()
    connection.close()

    return {
        "success": True,
        "user": {"id": user_id, "tenant_id": tenant_id, "name": name, "email": email, "role": role},
    }


def authenticate_user(email: str, password: str):
    email = (email or "").strip().lower()

    connection = get_connection()
    cursor = connection.cursor()
    user = cursor.execute(
        "SELECT id, tenant_id, name, email, role, password_hash FROM users WHERE email = ? AND is_active = 1",
        (email,),
    ).fetchone()
    connection.close()

    if not user:
        return {"success": False, "message": "Invalid email or password."}

    stored_hash = user[5]
    if not verify_password(password or "", stored_hash):
        return {"success": False, "message": "Invalid email or password."}

    user_dict = {"id": user[0], "tenant_id": user[1], "name": user[2], "email": user[3], "role": user[4]}
    return {"success": True, "user": user_dict}


def get_tenant_by_id(tenant_id: int):
    connection = get_connection()
    tenant = connection.execute(
        "SELECT id, name, slug, plan, is_active FROM tenants WHERE id = ?",
        (tenant_id,),
    ).fetchone()
    connection.close()
    if not tenant:
        return None
    return {"id": tenant[0], "name": tenant[1], "slug": tenant[2], "plan": tenant[3], "is_active": bool(tenant[4])}
