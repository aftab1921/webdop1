import os
import sqlite3
import random
from flask import Flask, render_template, request, redirect, session, url_for, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime



app = Flask(__name__)
app.secret_key = 'webdop_secret_key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ----------------------------- DATABASE CONNECTION ----------------------------- #
def get_db():
    conn = sqlite3.connect('webdop.db')
    conn.row_factory = sqlite3.Row
    return conn

# ----------------------------- INIT DB SCHEMA ----------------------------- #
def init_db():
    conn = get_db()
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        email TEXT,
        joined_at TEXT
    );

    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        image TEXT,
        caption TEXT,
        created_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS likes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        post_id INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (post_id) REFERENCES posts(id)
    );

    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        post_id INTEGER,
        comment TEXT,
        created_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (post_id) REFERENCES posts(id)
    );
    ''')
    conn.commit()

# ----------------------------- ROUTES ----------------------------- #

@app.route('/')
def home():
    return redirect('/dashboard') if 'username' in session else redirect('/login')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email    = request.form['email']
        password = generate_password_hash(request.form['password'])
        joined_at = datetime.now().strftime('%Y-%m-%d')

        try:
            conn = get_db()
            conn.execute('INSERT INTO users (username, password, email, joined_at) VALUES (?, ?, ?, ?)',
                         (username, password, email, joined_at))
            conn.commit()
            flash('Signup successful. Please log in.', 'success')
            return redirect('/login')
        except sqlite3.IntegrityError:
            flash('Username already taken.', 'danger')

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password_input = request.form['password']

        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

        if user and check_password_hash(user['password'], password_input):
            session['username'] = user['username']
            session['user_id'] = user['id']
            return redirect('/dashboard')
        else:
            flash('Invalid credentials', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect('/login')

    conn = get_db()
    posts = conn.execute('''
        SELECT posts.id, users.username, posts.image, posts.caption, posts.created_at
        FROM posts JOIN users ON posts.user_id = users.id
        ORDER BY posts.created_at DESC
    ''').fetchall()

    likes = {
        post['id']: conn.execute('SELECT COUNT(*) FROM likes WHERE post_id = ?', (post['id'],)).fetchone()[0]
        for post in posts
    }

    comments = {
        post['id']: conn.execute('SELECT comment FROM comments WHERE post_id = ?', (post['id'],)).fetchall()
        for post in posts
    }

    top_users = conn.execute('SELECT username FROM users ORDER BY id DESC LIMIT 10').fetchall()

    return render_template('dashboard.html', posts=posts, likes=likes, comments=comments, top_users=[u['username'] for u in top_users])

@app.route('/upload', methods=['POST'])
def upload():
    if 'username' not in session:
        return redirect('/login')

    image = request.files['image']
    caption = request.form['caption']

    if image:
        filename = datetime.now().strftime("%Y%m%d%H%M%S_") + str(random.randint(10000, 99999)) + os.path.splitext(image.filename)[1]
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image.save(image_path)

        conn = get_db()
        conn.execute(
            "INSERT INTO posts (user_id, image, caption, created_at) VALUES (?, ?, ?, ?)",
            (session['user_id'], filename, caption, datetime.now())
        )
        conn.commit()

    return redirect('/dashboard')

@app.route('/profile/<username>')
def profile(username):
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

    if not user:
        return "User not found", 404

    posts = conn.execute('SELECT * FROM posts WHERE user_id = ? ORDER BY created_at DESC', (user['id'],)).fetchall()
    return render_template('profile.html', user=user, posts=posts)

@app.route('/like/<int:post_id>', methods=['POST'])
def like(post_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 403

    conn = get_db()
    existing = conn.execute('SELECT * FROM likes WHERE user_id = ? AND post_id = ?', (session['user_id'], post_id)).fetchone()
    if not existing:
        conn.execute("INSERT INTO likes (user_id, post_id) VALUES (?, ?)", (session['user_id'], post_id))
        conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM likes WHERE post_id = ?", (post_id,)).fetchone()[0]
    return jsonify({'likes': count})

@app.route('/comment/<int:post_id>', methods=['POST'])
def comment(post_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json()
    comment_text = data.get('comment', '')
    conn = get_db()
    conn.execute("INSERT INTO comments (user_id, post_id, comment, created_at) VALUES (?, ?, ?, ?)",
                 (session['user_id'], post_id, comment_text, datetime.now()))
    conn.commit()
    return jsonify({'success': True})

@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    if not query.startswith('#'):
        flash('Search must start with a hashtag (#)', 'warning')
        return redirect('/dashboard')

    conn = get_db()
    posts = conn.execute('''
        SELECT posts.id, users.username, posts.image, posts.caption, posts.created_at
        FROM posts JOIN users ON posts.user_id = users.id
        WHERE caption LIKE ?
        ORDER BY posts.created_at DESC
    ''', ('%' + query + '%',)).fetchall()

    likes = {post['id']: conn.execute('SELECT COUNT(*) FROM likes WHERE post_id = ?', (post['id'],)).fetchone()[0] for post in posts}
    comments = {post['id']: conn.execute('SELECT comment FROM comments WHERE post_id = ?', (post['id'],)).fetchall() for post in posts}

    return render_template('dashboard.html', posts=posts, likes=likes, comments=comments, top_users=[])

# ----------------------------- INIT ----------------------------- #
if __name__ == '__main__':
    init_db()
    app.run(debug=True)
