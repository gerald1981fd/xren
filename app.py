import os
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ["FLASK_SECRET_KEY"]

# --- Supabase ------------------------------------------------------------
SUPABASE_URL = os.environ["DB_LINK"]
SUPABASE_ANON_KEY = os.environ["DB_KEY"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SERVICE_ROLE_KEY"]

# Публічний клієнт - лише читання (для index.html)
public_client: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
# Адмін-клієнт - обходить RLS, використовується тільки після логіна
admin_client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# --- Логін адміна: НЕ в базі даних, а у змінних середовища сервера -------
ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped


def calc_final_price(price: float, discount_percent: float) -> float:
    return round(float(price) * (1 - float(discount_percent or 0) / 100), 2)


def read_product_form():
    """Зчитує та валідує дані форми товару."""
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    price_raw = request.form.get("price", "").strip()
    discount_raw = request.form.get("discount_percent", "0").strip()
    image_url = request.form.get("image_url", "").strip()

    errors = []
    if not name:
        errors.append("Назва товару обов'язкова")
    try:
        price = float(price_raw)
        if price < 0:
            errors.append("Ціна не може бути від'ємною")
    except ValueError:
        price = None
        errors.append("Ціна вказана невірно")
    try:
        discount_percent = float(discount_raw or 0)
        if not (0 <= discount_percent <= 100):
            errors.append("Знижка має бути в межах 0-100%")
    except ValueError:
        discount_percent = None
        errors.append("Знижка вказана невірно")

    data = {
        "name": name,
        "description": description,
        "price": price,
        "discount_percent": discount_percent,
        "image_url": image_url,
    }
    return data, errors


# --- Публічна сторінка -----------------------------------------------------
@app.route("/")
def index():
    result = (
        public_client.table("products")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    products = result.data or []
    for p in products:
        p["final_price"] = calc_final_price(p["price"], p.get("discount_percent"))
    return render_template("index.html", products=products)


# --- Авторизація адміна -----------------------------------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin_panel"))
        flash("Невірний логін або пароль")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("index"))


# --- Адмін-панель: список + додавання -----------------------------------------
@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin_panel():
    if request.method == "POST":
        data, errors = read_product_form()
        if errors:
            for e in errors:
                flash(e)
        else:
            admin_client.table("products").insert(data).execute()
            flash("Товар додано")
        return redirect(url_for("admin_panel"))

    result = (
        admin_client.table("products")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    products = result.data or []
    return render_template("admin.html", products=products)


# --- Адмін-панель: редагування ------------------------------------------------
@app.route("/admin/edit/<int:product_id>", methods=["GET", "POST"])
@login_required
def admin_edit(product_id):
    if request.method == "POST":
        data, errors = read_product_form()
        if errors:
            for e in errors:
                flash(e)
            return redirect(url_for("admin_edit", product_id=product_id))
        admin_client.table("products").update(data).eq("id", product_id).execute()
        flash("Товар оновлено")
        return redirect(url_for("admin_panel"))

    result = (
        admin_client.table("products").select("*").eq("id", product_id).single().execute()
    )
    product = result.data
    if not product:
        flash("Товар не знайдено")
        return redirect(url_for("admin_panel"))
    return render_template("admin_edit.html", product=product)


# --- Адмін-панель: видалення --------------------------------------------------
@app.route("/admin/delete/<int:product_id>", methods=["POST"])
@login_required
def admin_delete(product_id):
    admin_client.table("products").delete().eq("id", product_id).execute()
    flash("Товар видалено")
    return redirect(url_for("admin_panel"))


if __name__ == "__main__":
    app.run(debug=True)