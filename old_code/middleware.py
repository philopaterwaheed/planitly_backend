from flask import session, jsonify

def login_required(func):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "Authentication required"}), 401
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper
