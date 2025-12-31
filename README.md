# Oposiciones BOE – Plataforma Web

Aplicación web desarrollada durante mis prácticas en equipo (5 integrantes) para consultar, filtrar y visualizar oposiciones publicadas en el BOE mediante técnicas de web scraping.

## Mi rol en el proyecto (Frontend Developer)

Este proyecto fue desarrollado en equipo durante mis prácticas.  
Yo fui responsable de toda la parte **Frontend**, incluyendo:

- Diseño de la interfaz (UI)
- Experiencia de usuario (UX)
- Maquetación con HTML/CSS
- Lógica de interacción en el cliente
- Integración del frontend con el backend (Flask + API interna)
- Validación de formularios y manejo de errores
- Estructura de plantillas y componentes

Mi objetivo fue crear una interfaz clara, usable y visualmente coherente para que los usuarios pudieran consultar oposiciones de forma sencilla.

## 🛠️ Tecnologías utilizadas

### Frontend (mi responsabilidad principal)
- HTML5
- CSS3
- JavaScript
- Jinja2 (plantillas)
- Diseño responsive

### Backend (trabajo del equipo)
- Python
- Flask
- Web Scraping con `requests` y `BeautifulSoup`
- SQLite

##  Funcionalidades principales

- Scraping automático de oposiciones del BOE
- Filtros por categoría, fecha y organismo
- Buscador dinámico
- Sistema de login/registro
- Panel de usuario
- Interfaz responsive

## Instalación y ejecución

Sigue estos pasos si quieres ejecutar el proyecto en local:

1. Clonar el repositorio:
git clone https://github.com/elaudy37-commits/oposiciones-boe.git

2. Entrar en la carpeta del proyecto:
cd oposiciones-boe

3. Crear un entorno virtual:
python -m venv venv

4. Activar el entorno virtual (Windows):
venv\Scripts\activate

5. Instalar dependencias:
pip install -r requirements.txt

6. Ejecutar la aplicación:
python scraping_BOE.py
