"""
VegBox - Simple Farmer-to-Customer Marketplace (Streamlit) with Local LLaMA 3.2 1B Chatbot
"""

import streamlit as st
import sqlite3
from pathlib import Path
from PIL import Image
import pandas as pd
import io
import base64
import datetime
import requests

# ------------------ Setup ------------------
DB_PATH = 'vegbox.db'
IMAGES_DIR = Path('images')
IMAGES_DIR.mkdir(exist_ok=True)

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()

cur.execute('''
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_name TEXT,
    title TEXT,
    description TEXT,
    price REAL,
    quantity INTEGER,
    image_path TEXT,
    created_at TEXT
)
''')

cur.execute('''
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT,
    items TEXT,
    total REAL,
    created_at TEXT
)
''')
conn.commit()

# ------------------ Demo Products ------------------

def insert_demo_products():
    cur.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()[0] == 0:
        demo_items = [
            ("Farmer A", "Tomatoes", "Fresh red tomatoes", 40.0, 50, None),
            ("Farmer B", "Potatoes", "Organic potatoes", 30.0, 40, None),
            ("Farmer C", "Carrots", "Crunchy carrots", 25.0, 60, None),
            ("Farmer D", "Spinach", "Green leafy spinach", 15.0, 30, None),
            ("Farmer E", "Cucumbers", "Fresh cucumbers", 20.0, 45, None)
        ]
        for farmer, title, desc, price, qty, img in demo_items:
            cur.execute(
                "INSERT INTO products (farmer_name, title, description, price, quantity, image_path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (farmer, title, desc, price, qty, img, datetime.datetime.now().isoformat())
            )
        conn.commit()

insert_demo_products()

# ------------------ Helpers ------------------

def save_image(uploaded_file):
    if uploaded_file is None:
        return None
    filename = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{uploaded_file.name}"
    path = IMAGES_DIR / filename
    with open(path, 'wb') as f:
        f.write(uploaded_file.getbuffer())
    return str(path)


def add_product(farmer_name, title, description, price, quantity, image_path):
    cur.execute(
        "INSERT INTO products (farmer_name, title, description, price, quantity, image_path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (farmer_name, title, description, price, quantity, image_path, datetime.datetime.now().isoformat())
    )
    conn.commit()


def get_products():
    cur.execute("SELECT id, farmer_name, title, description, price, quantity, image_path FROM products ORDER BY id DESC")
    rows = cur.fetchall()
    columns = ['id', 'farmer_name', 'title', 'description', 'price', 'quantity', 'image_path']
    return [dict(zip(columns, r)) for r in rows]


def update_product_quantity(product_id, new_qty):
    cur.execute("UPDATE products SET quantity = ? WHERE id = ?", (new_qty, product_id))
    conn.commit()


def create_order(customer_name, items, total):
    cur.execute("INSERT INTO orders (customer_name, items, total, created_at) VALUES (?, ?, ?, ?)",
                (customer_name, items, total, datetime.datetime.now().isoformat()))
    conn.commit()
    return cur.lastrowid


def render_image(path, width=200):
    try:
        img = Image.open(path)
        st.image(img, use_column_width=False, width=width)
    except Exception:
        st.text("[image not available]")

# ------------------ Local LLaMA Chatbot ------------------

def llama_chatbot(prompt: str) -> str:
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "llama3.2:1b", "prompt": prompt, "stream": False}
        )
        if response.status_code == 200:
            return response.json().get("response", "").strip()
        else:
            return f"[Error {response.status_code}] Could not reach local model."
    except Exception as e:
        return f"[Exception] {str(e)}"

# ------------------ UI ------------------

st.set_page_config(page_title='VegBox - Farmer Marketplace', page_icon='🥕', layout='wide')

st.markdown("""
# 🥕 VegBox
A simple farmer-to-customer marketplace demo built with Streamlit — now with a local LLaMA 3.2 1B chatbot.
""")

st.sidebar.title('Quick Actions')
role = st.sidebar.radio('I am a', ['Customer', 'Farmer', 'Visitor'])

if 'cart' not in st.session_state:
    st.session_state.cart = {}

if st.sidebar.button('Clear cart'):
    st.session_state.cart = {}
    st.sidebar.success('Cart cleared')

st.sidebar.markdown('---')
st.sidebar.subheader('VegBot — LLaMA 3.2 1B')
chat_input = st.sidebar.text_input('Ask VegBot something', key='chat_input')
if st.sidebar.button('Send', key='send_chat'):
    if chat_input.strip():
        response = llama_chatbot(chat_input)
        st.sidebar.info(response)
    else:
        st.sidebar.warning('Type a question first')

st.sidebar.markdown('---')

# ------------------ Farmer Panel ------------------
if role == 'Farmer':
    st.header('Farmer Panel — Add a new product')
    with st.form('add_product_form'):
        farmer_name = st.text_input('Farmer name', value='')
        col1, col2 = st.columns([2,1])
        with col1:
            title = st.text_input('Veg/Item name')
            description = st.text_area('Short description', max_chars=200)
        with col2:
            price = st.number_input('Price (₹ per unit)', min_value=0.0, format='%.2f')
            quantity = st.number_input('Quantity available', min_value=0, step=1)
            image_file = st.file_uploader('Image (optional)', type=['png','jpg','jpeg'])
        submitted = st.form_submit_button('Add product')
        if submitted:
            if not title or not farmer_name:
                st.error('Please add your name and a product title')
            else:
                img_path = save_image(image_file)
                add_product(farmer_name, title, description, float(price), int(quantity), img_path)
                st.success(f'Added {title} — visible in marketplace!')

# ------------------ Customer / Marketplace ------------------
elif role == 'Customer' or role == 'Visitor':
    st.header('Marketplace — Buy fresh vegetables')
    products = get_products()
    if not products:
        st.info('No products listed yet.')
    else:
        cols_per_row = 3
        rows = [products[i:i+cols_per_row] for i in range(0, len(products), cols_per_row)]
        for row in rows:
            cols = st.columns(cols_per_row)
            for idx, p in enumerate(row):
                with cols[idx]:
                    st.markdown(f"**{p['title']}**")
                    if p['image_path']:
                        render_image(p['image_path'], width=180)
                    st.write(p['description'])
                    st.write(f"Seller: {p['farmer_name']}")
                    st.write(f"Price: ₹{p['price']}  |  Stock: {p['quantity']}")
                    qty = st.number_input(f'Add qty ({p["id"]})', min_value=0, max_value=int(p['quantity']), key=f"qty_{p['id']}")
                    if st.button('Add to cart', key=f"add_{p['id']}"):
                        if qty <= 0:
                            st.warning('Select quantity > 0')
                        elif qty > p['quantity']:
                            st.error('Not enough stock')
                        else:
                            cart = st.session_state.cart
                            cart[str(p['id'])] = cart.get(str(p['id']), 0) + int(qty)
                            st.session_state.cart = cart
                            st.success(f'Added {qty} x {p["title"]} to cart')

    st.sidebar.header('Your Cart')
    cart = st.session_state.cart
    if not cart:
        st.sidebar.info('Cart is empty')
    else:
        df_rows = []
        total = 0.0
        for pid, qty in cart.items():
            cur.execute('SELECT id, title, price, quantity FROM products WHERE id=?', (int(pid),))
            r = cur.fetchone()
            if r:
                _, title, price, available = r
                subtotal = price * qty
                df_rows.append({'Product': title, 'Qty': qty, 'UnitPrice': price, 'Subtotal': subtotal})
                total += subtotal
        cart_df = pd.DataFrame(df_rows)
        st.sidebar.dataframe(cart_df)
        st.sidebar.markdown(f'**Total: ₹{total:.2f}**')

        cust_name = st.sidebar.text_input('Your name for order')
        if st.sidebar.button('Checkout'):
            if not cust_name:
                st.sidebar.error('Please enter your name')
            else:
                items_desc = ', '.join([f"{r['Product']} x{r['Qty']}" for r in df_rows])
                order_id = create_order(cust_name, items_desc, total)
                for pid, qty in cart.items():
                    cur.execute('SELECT quantity FROM products WHERE id=?', (int(pid),))
                    r = cur.fetchone()
                    if r:
                        new_q = max(0, r[0] - qty)
                        update_product_quantity(int(pid), new_q)
                st.sidebar.success(f'Order #{order_id} placed — total ₹{total:.2f}')

                receipt_df = cart_df.copy()
                receipt_df.loc[len(receipt_df.index)] = ['TOTAL', '', '', total]
                csv = receipt_df.to_csv(index=False)
                b64 = base64.b64encode(csv.encode()).decode()
                href = f'<a href="data:file/csv;base64,{b64}" download="order_{order_id}.csv">Download receipt (CSV)</a>'
                st.sidebar.markdown(href, unsafe_allow_html=True)

                st.session_state.cart = {}

st.markdown('---')
with st.expander('Admin: Recent orders (demo)'):
    cur.execute('SELECT id, customer_name, items, total, created_at FROM orders ORDER BY id DESC LIMIT 10')
    orders = cur.fetchall()
    if orders:
        df = pd.DataFrame(orders, columns=['id','customer_name','items','total','created_at'])
        st.dataframe(df)
    else:
        st.write('No orders yet')

st.markdown('---')
st.caption('Tip: Customize this demo by adding authentication, delivery info, and a real payment gateway to make it production-ready.')
