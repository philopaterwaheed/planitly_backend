import re
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.getenv(
    'SECRET_KEY', 'bf0060a011ea5949a54477076c3a616dcc3ae6145a8dd93bf731b5d5463e0de1')

client = MongoClient('mongodb://localhost:27017/')
db = client['planitly']
users_collection = db['users']

EMAIL_REGEX = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'


@app.route('/')
def home():
    if 'username' in session:
        return render_template('home.html', username=session['username'])
    return redirect(url_for('login'))


@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return jsonify({"message": "Invalid request", "status": "error"}), 400

    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if not username or not email or not password:
        return jsonify({"message": "All fields are required", "status": "error"}), 400

    if not re.match(EMAIL_REGEX, email):
        return jsonify({"message": "please enter valid email", "status": "error"}), 400

    if not re.match(r"^(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&^#_+=<>.,;:|\\/-])[A-Za-z\d@$!%*?&^#_+=<>.,;:|\\/-]{8,}$", password):
        return jsonify({"message": "Password must be at least 8 characters long, with one uppercase letter, one number, and one special character.", "status": "error"}), 400

    if users_collection.find_one({'email': email}):
        return jsonify({"message": "Email already registered", "status": "error"}), 400

    try:
        hashed_password = generate_password_hash(password)
        users_collection.insert_one({
            'username': username,
            'email': email,
            'password': hashed_password
        })
        return jsonify({"message": "Registration successful!", "status": "success"}), 201
    except Exception:
        return jsonify({"message": "An error occurred during registration", "status": "error"}), 500


@app.route('/login', methods=['GET', 'POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({"message": "Invalid request", "status": "error"}), 400

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"message": "Email and password are required", "status": "error"}), 400

    user = users_collection.find_one({'email': email})

    if user and check_password_hash(user['password'], password):
        session['username'] = user['username']
        return jsonify({"message": "Login successful!", "status": "success"}), 200
    return jsonify({"message": "Invalid credentials", "status": "error"}), 401


@app.route('/logout')
def logout():
    session.pop('username', None)
    return jsonify({"message": "Logged out successfully", "status": "success"}), 200


if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true')
