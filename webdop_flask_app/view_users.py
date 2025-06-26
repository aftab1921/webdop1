import sqlite3

# Connect to the SQLite database
conn = sqlite3.connect('webdop.db')
cursor = conn.cursor()

# Ensure table exists (optional safeguard)
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        email TEXT UNIQUE,
        joined_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')

# Fetch all user data
cursor.execute("SELECT id, username, password, email, joined_at FROM users")
users = cursor.fetchall()

# Print formatted output
print("\n--- User Records ---")
for user in users:
    print(f"ID: {user[0]}")
    print(f"Username: {user[1]}")
    print(f"Password: {user[2]}")
    print(f"Email: {user[3]}")
    print(f"Joined: {user[4]}")
    print("-" * 30)

conn.close()
