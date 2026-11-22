
import re

import psycopg
from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash

from saas_database import get_db

saas_auth = Blueprint("saas_auth", __name__, url_prefix="/api/auth")


def valid_email(email):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))


@saas_auth.route("/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True) or {}

    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    name = str(data.get("name", "")).strip()

    if not valid_email(email):
        return jsonify({"error": "Enter a valid email address"}), 400

    if len(password) < 12:
        return jsonify({"error": "Password must be at least 12 characters"}), 400

    password_hash = generate_password_hash(password)

    try:
        with get_db() as db:
            cursor = db.execute(
                """
                INSERT INTO users
                    (email, password_hash, name, plan, subscription_status)
                VALUES (%s, %s, %s, 'free', 'active')
                RETURNING id
                """,
                (email, password_hash, name),
            )

            user_id = cursor.fetchone()["id"]

            db.execute(
                """
                INSERT INTO subscriptions (user_id, plan, status)
                VALUES (%s, 'free', 'active')
                """,
                (user_id,),
            )

        return jsonify({
            "message": "Account created successfully",
            "user_id": user_id,
        }), 201

    except psycopg.errors.UniqueViolation:
        return jsonify({"error": "Email already registered"}), 409


@saas_auth.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}

    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    with get_db() as db:
        user = db.execute(
            """
            SELECT id, email, password_hash, name
            FROM users
            WHERE email = %s
            """,
            (email,),
        ).fetchone()

    if not user or not check_password_hash(
        user["password_hash"] or "", password
    ):
        return jsonify({"error": "Invalid email or password"}), 401

    session.clear()
    session["user_id"] = user["id"]

    return jsonify({
        "message": "Login successful",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
        },
    })


@saas_auth.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully"})


@saas_auth.route("/me", methods=["GET"])
def me():
    user_id = session.get("user_id")

    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    with get_db() as db:
        user = db.execute(
            """
            SELECT id, email, name
            FROM users
            WHERE id = %s
            """,
            (user_id,),
        ).fetchone()

    if not user:
        session.clear()
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
    })

