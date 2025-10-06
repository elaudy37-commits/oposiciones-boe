"""scraping_mundo.py

Aplicación Flask que:
- Raspa oposiciones del BOE usando requests + BeautifulSoup
- Guarda resultados en SQLite
- Muestra tabla con Bootstrap en plantilla externa (/templates/index.html)
- Permite búsqueda por texto y filtrado
"""

import sqlite3
from datetime import datetime

import requests
from flask import Flask, request, g, redirect, url_for, render_template
from bs4 import BeautifulSoup

DB_PATH = 'oposiciones.db'
MAX_ITEMS = 50
app = Flask(__name__)  # Cambiar nombre

# --------------------
# Database helpers
# --------------------


def get_db():
    """Devuelve la conexión a la base de datos SQLite."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(_):
    """Cierra la conexión a la base de datos al finalizar la solicitud."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def init_db():
    """Inicializa la tabla de oposiciones si no existe."""
    db = get_db()
    db.execute('''
        CREATE TABLE IF NOT EXISTS oposiciones (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               identificador TEXT NOT NULL,
               control TEXT,
               titulo TEXT,
               url_html TEXT UNIQUE
        )
    ''')
    db.commit()


# --------------------
# Scraper BOE
# --------------------

def scrape_boe(max_items=MAX_ITEMS):
    """"Raspa oposiciones del BOE y las guarda en SQLite"""
    init_db()
    db = get_db()
    collected = 0

    # Construir URL con la fecha actual
    hoy = datetime.today().strftime("%Y%m%d")
    boe_url = f'https://www.boe.es/datosabiertos/api/boe/sumario/{hoy}'

    print(boe_url)

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/118.0.5993.118 Safari/537.3',
            'Accept': 'application/xml, text/xml, */*; q=0.01',
        }
        r = requests.get(boe_url, headers=headers, timeout=10)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"Error al obtener el XML BOE: {e}")
        return 0

    soup = BeautifulSoup(r.content, 'xml')

    # Buscar las entradas de tipo <item>
    items = list(soup.find_all(['item']))[:max_items]

    for item in items:
        identificador = item.find("identificador")
        control = item.find("control")
        titulo = item.find("titulo")
        url_html = item.find("url_html")

        identificador = identificador.text.strip() if identificador else None
        control = control.text.strip() if control else None
        titulo = titulo.text.strip() if titulo else None
        url_html = url_html.text.strip() if url_html else None

        if not identificador or not url_html:
            continue

        try:
            db.execute('''
                INSERT INTO oposiciones (identificador, control, titulo, url_html)
                VALUES (?, ?, ?, ?)
            ''', (identificador, control, titulo, url_html))
            db.commit()
            collected += 1
        except sqlite3.IntegrityError:
            continue  # URL ya existe

    return collected
# --------------------
# Flask routes
# --------------------


@app.route('/')
def index():
    """Muestra la tabla de oposiciones, con búsqueda y filtro."""
    init_db()
    q = request.args.get('q', '').strip()

    db = get_db()
    params = []
    sql = 'SELECT * FROM oposiciones'

    if q:
        sql += ' WHERE (identificador LIKE ? OR control LIKE ? OR titulo LIKE ? OR url_html LIKE ?)'
        likeq = f'%{q}%'
        params.extend([likeq, likeq, likeq, likeq])

    sql += ' ORDER BY id DESC LIMIT ?'
    params.append(MAX_ITEMS)

    cur = db.execute(sql, params)
    rows = cur.fetchall()

    return render_template('index.html', rows=rows, q=q)


@app.route('/scrape')
def do_scrape():
    """Ejecuta el scraper y redirige a la página principal."""
    init_db()
    scrape_boe(MAX_ITEMS)
    return redirect(url_for('index'))


if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True)
