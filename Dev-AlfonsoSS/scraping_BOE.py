"""scraping_boe.py

Aplicación Flask para Web Scraping del BOE (Boletín Oficial del Estado)

Funcionalidades principales:
- Extrae oposiciones y concursos de la API oficial del BOE
- Almacena datos en base de datos SQLite local
- Interfaz web responsive con Bootstrap 5
- Organización por departamentos en vista de tarjetas
- Enlaces directos a documentos PDF oficiales
- Sistema de actualización manual de datos

Autor: Desarrollado por franSM, Cristóbal Delgado Romero.
Versión: 1.0
Fecha: 2025
"""

import sqlite3
from datetime import datetime, timedelta
import requests
from flask import Flask, request, g, redirect, url_for, render_template
from bs4 import BeautifulSoup

DB_PATH = 'oposiciones.db'
app = Flask(__name__)

# --------------------
# Jinja2 filters
# --------------------

@app.template_filter('format_date')
def format_date_filter(date_str):
    """Convierte fecha de formato YYYYMMDD a dd/mm/yyyy."""
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
# Database helpers
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
    db.execute('''
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
    ''')
    db.commit()


# --------------------
# Scraper BOE
# --------------------

def scrape_boe():
    """Extrae oposiciones del BOE y las almacena en SQLite."""
    init_db()
    db = get_db()
    collected = 0

    fecha = datetime.today()

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept': 'application/xml, text/xml, */*; q=0.01',
    }

    for _ in range(7):
        hoy = fecha.strftime('%Y%m%d')
        boe_url = f'https://www.boe.es/datosabiertos/api/boe/sumario/{hoy}'
        try:
            r = requests.get(boe_url, headers=headers, timeout=10)
            if r.status_code == 200:
                print(f" BOE encontrado {boe_url}")
                break
            print(f" No disponible para {hoy}. Probando día anterior.")
        except requests.RequestException as e:
            print(f" Error al obtener {boe_url}: {e}")
        fecha -= timedelta(days=1)
    else:
        print(" No se encontró ningún BOE reciente.")
        return 0

    soup = BeautifulSoup(r.content, 'xml')
    seccion = soup.find("seccion", {"codigo": "2B"})
    if not seccion:
        print("No se encontró la sección 2B en el XML.")
        return 0

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
            db.execute('''
                INSERT INTO oposiciones (identificador, control, titulo, url_html, url_pdf, departamento, fecha)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (identificador, control, titulo, url_html, url_pdf, departamento, hoy))
            db.commit()
            collected += 1
        except sqlite3.IntegrityError:
            continue  

    return collected


# --------------------
# Flask routes
# --------------------

@app.route('/')
def index():
    init_db()
    db = get_db()
    deps = db.execute(
        'SELECT DISTINCT departamento FROM oposiciones WHERE departamento IS NOT NULL ORDER BY departamento'
    ).fetchall()
    return render_template('index.html', departamentos=deps)


@app.route('/departamento/<nombre>')
def mostrar_departamento(nombre):
    """Vista detallada de oposiciones por departamento con paginación y filtro por fecha."""
    init_db()
    db = get_db()

    page = request.args.get('page', 1, type=int)
    per_page = 15
    offset = (page - 1) * per_page

    # --- NUEVO: filtros de fecha ---
    desde = request.args.get('desde')
    hasta = request.args.get('hasta')

    query = 'SELECT * FROM oposiciones WHERE departamento = ?'
    params = [nombre]

    if desde and hasta:
        desde_fmt = datetime.strptime(desde, "%Y-%m-%d").strftime("%Y%m%d")
        hasta_fmt = datetime.strptime(hasta, "%Y-%m-%d").strftime("%Y%m%d")
        query += ' AND fecha BETWEEN ? AND ?'
        params += [desde_fmt, hasta_fmt]

    query += ' ORDER BY fecha DESC, id DESC LIMIT ? OFFSET ?'
    params += [per_page, offset]

    cur = db.execute(query, params)
    rows = cur.fetchall()

    # Total con el mismo filtro
    total_query = 'SELECT COUNT(*) FROM oposiciones WHERE departamento = ?'
    total_params = [nombre]
    if desde and hasta:
        total_query += ' AND fecha BETWEEN ? AND ?'
        total_params += [desde_fmt, hasta_fmt]

    total = db.execute(total_query, total_params).fetchone()[0]
    total_pages = (total + per_page - 1) // per_page

    return render_template(
        'tarjeta.html',
        departamento=nombre,
        rows=rows,
        page=page,
        total_pages=total_pages
    )


@app.route('/scrape')
def do_scrape():
    init_db()
    scrape_boe()
    return redirect(url_for('index'))


if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True)
