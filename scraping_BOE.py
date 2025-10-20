"""scraping_boe.py

Aplicación Flask para Web Scraping del BOE (Boletín Oficial del Estado)
con sistema de usuarios (sign up / login) y notificación por email de
nuevas oposiciones detectadas.

Autor original: franSM, Cristóbal Delgado Romero
Ampliado con auth + email: 2025
"""

import os
import sqlite3
from datetime import datetime, timedelta

import requests
from flask import (
    Flask, request, g, redirect, url_for, render_template, session, flash
)
from bs4 import BeautifulSoup
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message

DB_PATH = 'oposiciones.db'
app = Flask(__name__)

# === Configuración básica (lee de variables de entorno) ===
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'cambia-esto')
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'localhost')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', '25'))
app.config['MAIL_USE_TLS'] = bool(int(os.getenv('MAIL_USE_TLS', '0')))
app.config['MAIL_USE_SSL'] = bool(int(os.getenv('MAIL_USE_SSL', '0')))
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', os.getenv('MAIL_USERNAME'))

mail = Mail(app)

# --------------------
# Jinja2 filters
# --------------------

@app.template_filter('format_date')
def format_date_filter(date_str):
    if not date_str or len(date_str) != 8:
        return date_str
    try:
        year = date_str[0:4]
        month = date_str[4:6]
        day = date_str[6:8]
        return f"{day}/{month}/{year}"
    except:
        return date_str

# --------------------
# Helpers DB
# --------------------

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(_):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    # Tabla oposiciones (igual que antes, con UNIQUE en url_html)
    db.execute("""
        CREATE TABLE IF NOT EXISTS oposiciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            identificador TEXT NOT NULL,
            control TEXT,
            titulo TEXT,
            url_html TEXT UNIQUE,
            url_pdf TEXT,
            departamento TEXT,
            fecha TEXT
        )
    """)
    # Tabla usuarios
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    db.commit()

# --------------------
# Helpers Auth
# --------------------

def current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    db = get_db()
    row = db.execute("SELECT id, email FROM users WHERE id = ?", (uid,)).fetchone()
    return row

def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            flash("Inicia sesión para continuar.", "warning")
            return redirect(url_for('login', next=request.path))
        return fn(*args, **kwargs)
    return wrapper

def create_user(email, password):
    db = get_db()
    db.execute(
        "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
        (email.lower(), generate_password_hash(password), datetime.utcnow().isoformat())
    )
    db.commit()

def find_user_by_email(email):
    db = get_db()
    return db.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()

# --------------------
# Email
# --------------------

def send_new_oposiciones_email(recipients, oposiciones):
    if not recipients or not oposiciones:
        return
    html = render_template('emails/nuevas_oposiciones.html', oposiciones=oposiciones)
    subject = f"{len(oposiciones)} nuevas oposiciones publicadas"
    msg = Message(subject=subject, recipients=recipients, html=html)
    mail.send(msg)

def all_user_emails():
    db = get_db()
    return [r['email'] for r in db.execute("SELECT email FROM users").fetchall()]

# --------------------
# Scraper BOE
# --------------------

def scrape_boe():
    """
    Devuelve una lista de dicts con las oposiciones NUEVAS insertadas.
    Cada item: {identificador, control, titulo, url_html, url_pdf, departamento, fecha}
    """
    init_db()
    db = get_db()
    newly_inserted = []

    fecha = datetime.today()

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/118.0.5993.118 Safari/537.36',
        'Accept': 'application/xml, text/xml, */*; q=0.01',
    }

    for _ in range(7):
        hoy = fecha.strftime('%Y%m%d')
        boe_url = f'https://www.boe.es/datosabiertos/api/boe/sumario/{hoy}'
        try:
            r = requests.get(boe_url, headers=headers, timeout=10)
            if r.status_code == 200:
                break
        except requests.RequestException:
            pass
        fecha -= timedelta(days=1)
    else:
        return []

    soup = BeautifulSoup(r.content, 'xml')
    seccion = soup.find("seccion", {"codigo": "2B"})
    if not seccion:
        return []

    items = seccion.find_all("item")

    for item in items:
        identificador_tag = item.find("identificador")
        control_tag = item.find("control")
        titulo_tag = item.find("titulo")
        url_html_tag = item.find("url_html")
        url_pdf_tag = item.find("url_pdf")

        identificador = identificador_tag.text.strip() if identificador_tag else None
        control = control_tag.text.strip() if control_tag else None
        titulo = titulo_tag.text.strip() if titulo_tag else None
        url_html = url_html_tag.text.strip() if url_html_tag else None
        url_pdf = url_pdf_tag.text.strip() if url_pdf_tag else None

        dept_parent = item.find_parent("departamento")
        departamento = dept_parent.get('nombre') if dept_parent and dept_parent.has_attr('nombre') else None

        try:
            db.execute(
                "INSERT INTO oposiciones (identificador, control, titulo, url_html, url_pdf, departamento, fecha) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (identificador, control, titulo, url_html, url_pdf, departamento, hoy)
            )
            db.commit()
            newly_inserted.append({
                "identificador": identificador,
                "control": control,
                "titulo": titulo,
                "url_html": url_html,
                "url_pdf": url_pdf,
                "departamento": departamento,
                "fecha": hoy
            })
        except sqlite3.IntegrityError:
            continue

    return newly_inserted

# --------------------
# Rutas Flask
# --------------------

@app.route('/')
def index():
    init_db()
    db = get_db()
    deps = db.execute(
        'SELECT DISTINCT departamento FROM oposiciones WHERE departamento IS NOT NULL ORDER BY departamento'
    ).fetchall()
    return render_template('index.html', departamentos=deps, user=current_user())

@app.route('/departamento/<nombre>')
def mostrar_departamento(nombre):
    init_db()
    db = get_db()

    page = request.args.get('page', 1, type=int)
    per_page = 15
    offset = (page - 1) * per_page

    total = db.execute(
        'SELECT COUNT(*) FROM oposiciones WHERE departamento = ?',
        (nombre,)
    ).fetchone()[0]

    cur = db.execute(
        'SELECT * FROM oposiciones WHERE departamento = ? ORDER BY fecha DESC, id DESC LIMIT ? OFFSET ?',
        (nombre, per_page, offset)
    )
    rows = cur.fetchall()

    total_pages = (total + per_page - 1) // per_page

    return render_template(
        'tarjeta.html',
        departamento=nombre,
        rows=rows,
        page=page,
        total_pages=total_pages,
        user=current_user()
    )

@app.route('/scrape')
@login_required
def do_scrape():
    init_db()
    new_items = scrape_boe()
    if new_items:
        recipients = all_user_emails()
        try:
            send_new_oposiciones_email(recipients, new_items)
            flash(f"Se han insertado {len(new_items)} nuevas oposiciones y se ha enviado el email.", "success")
        except Exception as e:
            flash(f"Se insertaron {len(new_items)} nuevas oposiciones, pero falló el envío de email: {e}", "warning")
    else:
        flash("No hay nuevas oposiciones hoy.", "info")
    return redirect(url_for('index'))

# --- Registro / Login ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    init_db()
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip()
        password = request.form.get('password') or ''
        if not email or not password:
            flash("Email y contraseña son obligatorios.", "danger")
            return render_template('register.html', user=current_user())
        if find_user_by_email(email):
            flash("Ese email ya está registrado.", "warning")
            return render_template('register.html', user=current_user())
        create_user(email, password)
        user = find_user_by_email(email)
        session['user_id'] = user['id']
        flash("Registro correcto. Sesión iniciada.", "success")
        return redirect(url_for('index'))
    return render_template('register.html', user=current_user())

@app.route('/login', methods=['GET', 'POST'])
def login():
    init_db()
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip()
        password = request.form.get('password') or ''
        user = find_user_by_email(email)
        if not user or not check_password_hash(user['password_hash'], password):
            flash("Credenciales inválidas.", "danger")
            return render_template('login.html', user=current_user())
        session['user_id'] = user['id']
        flash("Sesión iniciada.", "success")
        next_url = request.args.get('next') or url_for('index')
        return redirect(next_url)
    return render_template('login.html', user=current_user())

@app.route('/logout')
@login_required
def logout():
    session.pop('user_id', None)
    flash("Sesión cerrada.", "info")
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True)

