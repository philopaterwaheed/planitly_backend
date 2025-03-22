from flask_jwt_extended import JWTManager, create_access_token, verify_jwt_in_request, get_jwt_identity
from models import User
from functools import wraps
from flask import Flask, request, jsonify, session

# Authentication Middleware
def login_required(func):
    """Middleware to protect routes that require authentication."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()  # Check if token is present
            user_id = get_jwt_identity()  # Extract user ID from token
            request.user_id = user_id
            user = User.objects(id=user_id).first()  # Fetch user from DB

            if not user:
                return jsonify({"error": "Unauthorized"}), 401

            return func(*args, **kwargs)  # Proceed to the actual route
        except Exception as e:
            return jsonify({"error": str(e)}), 401

    return wrapper  # Database Models

