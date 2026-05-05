from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
from datetime import datetime, timedelta
import os
from collections import defaultdict

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

    c.execute('''
    CREATE TABLE IF NOT EXISTS sales_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sales_id INTEGER,
        product_id INTEGER,
        quantity INTEGER DEFAULT 1,
        price REAL,
        FOREIGN KEY(sales_id) REFERENCES sales(id),
        FOREIGN KEY(product_id) REFERENCES products(id)
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS stocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER UNIQUE,
        quantity INTEGER,
        FOREIGN KEY(product_id) REFERENCES products(id)
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
    product_id = c.lastrowid
    
    # Add default stock
    c.execute("INSERT INTO stocks (product_id, quantity) VALUES (?, ?)", (product_id, 0))
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

    current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO sales (total, date) VALUES (?, ?)",
              (total, current_date))
    sales_id = c.lastrowid
    
    # Add sales items
    for item_id in selected_items:
        c.execute("SELECT price FROM products WHERE id=?", (item_id,))
        price = c.fetchone()[0]
        c.execute("INSERT INTO sales_items (sales_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
                  (sales_id, item_id, 1, price))

    conn.commit()
    conn.close()

    return render_template('bill.html', total=total, current_date=current_date)

# ==================== STOCKS MANAGEMENT ====================

@app.route('/stocks')
def stocks():
    search_query = request.args.get('q', '').strip()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    sql = '''SELECT p.id, p.name, p.price, COALESCE(s.quantity, 0)
             FROM products p
             LEFT JOIN stocks s ON p.id = s.product_id'''
    params = ()
    if search_query:
        sql += ' WHERE p.name LIKE ?'
        params = (f'%{search_query}%',)

    c.execute(sql, params)
    stocks_data = c.fetchall()
    conn.close()
    return render_template('stocks.html', stocks_data=stocks_data, search_query=search_query)

@app.route('/add_stock', methods=['POST'])
def add_stock():
    product_id = request.form['product_id']
    quantity = request.form['quantity']

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE stocks SET quantity = quantity + ? WHERE product_id = ?", (int(quantity), product_id))
    conn.commit()
    conn.close()

    return redirect(url_for('stocks'))

@app.route('/update_stock/<int:product_id>', methods=['POST'])
def update_stock(product_id):
    quantity = request.form['quantity']

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE stocks SET quantity = ? WHERE product_id = ?", (int(quantity), product_id))
    conn.commit()
    conn.close()

    return redirect(url_for('stocks'))

@app.route('/remove_stock/<int:product_id>', methods=['POST'])
def remove_stock(product_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM stocks WHERE product_id = ?", (product_id,))
    c.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()

    return redirect(url_for('stocks'))

# ==================== DASHBOARD & ANALYTICS ====================

@app.route('/dashboard')
def dashboard():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Aggregate totals
    c.execute("SELECT COUNT(*), SUM(total) FROM sales")
    total_sales_count, total_sales_amount = c.fetchone()
    total_sales_count = total_sales_count or 0
    total_sales_amount = total_sales_amount or 0

    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT SUM(total) FROM sales WHERE date LIKE ?", (f"{today}%",))
    today_sales = c.fetchone()[0] or 0

    week_start = datetime.now() - timedelta(days=datetime.now().weekday())
    c.execute("SELECT SUM(total) FROM sales WHERE date >= ?", (week_start.strftime("%Y-%m-%d") + "%",))
    week_sales = c.fetchone()[0] or 0

    month_start = datetime.now().replace(day=1)
    c.execute("SELECT SUM(total) FROM sales WHERE date >= ?", (month_start.strftime("%Y-%m-%d") + "%",))
    month_sales = c.fetchone()[0] or 0

    year_start = datetime.now().replace(month=1, day=1)
    c.execute("SELECT SUM(total) FROM sales WHERE date >= ?", (year_start.strftime("%Y-%m-%d") + "%",))
    year_sales = c.fetchone()[0] or 0

    c.execute("SELECT date, total FROM sales ORDER BY date")
    sales_raw = c.fetchall()

    daily_sales = defaultdict(float)
    weekly_sales = defaultdict(float)
    monthly_sales = defaultdict(float)
    yearly_sales = defaultdict(float)

    for date, total in sales_raw:
        dt = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
        daily_sales[dt.strftime("%Y-%m-%d")] += total
        iso_year, iso_week, _ = dt.isocalendar()
        weekly_sales[f"{iso_year}-W{iso_week:02d}"] += total
        monthly_sales[dt.strftime("%Y-%m")] += total
        yearly_sales[dt.strftime("%Y")] += total

    c.execute('''SELECT p.name, SUM(si.quantity) as qty
                 FROM sales_items si
                 JOIN products p ON si.product_id = p.id
                 GROUP BY p.id
                 ORDER BY qty DESC
                 LIMIT 10''')
    top_products = c.fetchall()
    top_labels = [product[0] for product in top_products]
    top_values = [product[1] for product in top_products]

    conn.close()

    return render_template('dashboard.html', 
                         total_sales_count=total_sales_count,
                         total_sales_amount=round(total_sales_amount, 2),
                         today_sales=round(today_sales, 2),
                         week_sales=round(week_sales, 2),
                         month_sales=round(month_sales, 2),
                         year_sales=round(year_sales, 2),
                         daily_sales=dict(sorted(daily_sales.items())),
                         weekly_sales=dict(sorted(weekly_sales.items())),
                         monthly_sales=dict(sorted(monthly_sales.items())),
                         yearly_sales=dict(sorted(yearly_sales.items())),
                         top_products=top_products,
                         top_labels=top_labels,
                         top_values=top_values)

# Run app (IMPORTANT FIX)
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)     # allow external access