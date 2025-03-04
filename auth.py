import re
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'bf0060a011ea5949a54477076c3a616dcc3ae6145a8dd93bf731b5d5463e0de1')

client = MongoClient('mongodb://localhost:27017/')
db = client['planitly']
users_collection = db['users']

EMAIL_REGEX = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'

@app.route('/')
def home():
    if 'username' in session:
        return render_template('home.html', username=session['username'])
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if not re.match(EMAIL_REGEX, email):
            flash("Invalid email format. Please provide a valid email address.", 'danger')
            return redirect(url_for('register'))

        if not re.match(r"^(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$", password):
            flash("Password must be at least 8 characters long, with one uppercase letter, one number, and one special character.", 'danger')
            return redirect(url_for('register'))

        if users_collection.find_one({'email': email}):
            flash('Email already registered', 'danger')
            return redirect(url_for('register'))

        try:
            hashed_password = generate_password_hash(password)
            users_collection.insert_one({
                'username': username,
                'email': email,
                'password': hashed_password
            })
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash('An error occurred during registration', 'danger')
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = users_collection.find_one({'email': email})

        if user and check_password_hash(user['password'], password):
            session['username'] = user['username']
            flash('Login successful', 'success')
            return redirect(url_for('home'))

        flash('Invalid credentials', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true')

"""
This is some sort of templates to test Auth before integrating it with the main login features

register.html : 
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Register</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha3/dist/css/bootstrap.min.css">
</head>
<body>
    <div class="container mt-5">
        <h2>Register</h2>
        {% with messages = get_flashed_messages() %}
          {% if messages %}
            <div class="alert alert-warning">
              {{ messages[0] }}
            </div>
          {% endif %}
        {% endwith %}
        <form method="POST">
            <div class="mb-3">
                <label for="username" class="form-label">Username</label>
                <input type="text" name="username" id="username" class="form-control" required>
            </div>
            <div class="mb-3">
                <label for="email" class="form-label">Email</label>
                <input type="email" name="email" id="email" class="form-control" required>
            </div>
            <div class="mb-3">
                <label for="password" class="form-label">Password</label>
                <input type="password" name="password" id="password" class="form-control" required>
            </div>
            <button type="submit" class="btn btn-primary">Register</button>
        </form>
        <a href="{{ url_for('login') }}">Already have an account? Login here.</a>
    </div>
</body>
</html>

login.html : 
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha3/dist/css/bootstrap.min.css">
</head>
<body>
    <div class="container mt-5">
        <h2>Login</h2>
        {% with messages = get_flashed_messages() %}
          {% if messages %}
            <div class="alert alert-danger">
              {{ messages[0] }}
            </div>
          {% endif %}
        {% endwith %}
        <form method="POST">
            <div class="mb-3">
                <label for="login_input" class="form-label">Username or Email</label>
                <input type="text" name="login_input" id="login_input" class="form-control" required>
            </div>
            <div class="mb-3">
                <label for="password" class="form-label">Password</label>
                <input type="password" name="password" id="password" class="form-control" required>
            </div>
            <button type="submit" class="btn btn-success">Login</button>
        </form>
        <a href="{{ url_for('register') }}">Don't have an account? Register here.</a>
    </div>
</body>
</html>

home.html : 
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Home</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha3/dist/css/bootstrap.min.css">
</head>
<body>
    <div class="container text-center mt-5">
        <h1>Welcome to Flask App</h1>
        <a href="{{ url_for('register') }}" class="btn btn-primary">Register</a>
        <a href="{{ url_for('login') }}" class="btn btn-success">Login</a>
    </div>
</body>
</html>
"""
