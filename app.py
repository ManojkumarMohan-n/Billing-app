from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)

# Ensure DB path works inside container
DB_PATH = os.path.join(os.getcwd(), 'database.db')

# DB setup
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price REAL
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        total REAL,
        date TEXT
    )
    ''')

    conn.commit()
    conn.close()

init_db()

# Home
@app.route('/')
def index():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM products")
    products = c.fetchall()
    conn.close()
    return render_template('index.html', products=products)

# Add product
@app.route('/add_product', methods=['POST'])
def add_product():
    name = request.form['name']
    price = request.form['price']

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO products (name, price) VALUES (?, ?)", (name, price))
    conn.commit()
    conn.close()

    return redirect(url_for('index'))

# Create bill
@app.route('/create_bill', methods=['POST'])
def create_bill():
    selected_items = request.form.getlist('product')
    total = 0

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    for item_id in selected_items:
        c.execute("SELECT price FROM products WHERE id=?", (item_id,))
        result = c.fetchone()
        if result:
            total += result[0]

    c.execute("INSERT INTO sales (total, date) VALUES (?, ?)",
              (total, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    conn.commit()
    conn.close()

    return render_template('bill.html', total=total)

# Run app (IMPORTANT FIX)
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))   # AWS dynamic port
    app.run(host='0.0.0.0', port=port)        # allow external access