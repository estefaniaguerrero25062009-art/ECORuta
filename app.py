import os
from bson.objectid import ObjectId
from bson.errors import InvalidId
from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from functools import wraps
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "ecoruta2026secretkey")

# ── Corrección #1: nombre de base de datos corregido a ecoruta_sql → ecoruta_nosql ──
# ── Corrección #4: contraseña movida a variable de entorno (.env) ──────────────────
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://gurn090625mmcrmla1_db_user:l4KpRbW3vJjaMvlb@cluster0.lqt9mjt.mongodb.net/")
client = MongoClient(MONGO_URI, server_api=ServerApi("1"))

db       = client["ecoruta_nosql"]   # #1 corrección: antes era ecoruta_sql
rutas    = db["rutas"]
reportes = db["reportes_ciudadanos"]

# Número de registros por página
PER_PAGE = 5

# ── usuarios fijos ─────────────────────────────────────────────────────────
USUARIOS = {
    "admin":     {"password": "ecoruta2026", "rol": "admin"},
    "ciudadano": {"password": "ecoruta2026", "rol": "ciudadano"}
}


# ── decoradores ────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario" not in session:
            return redirect(url_for("login"))
        if session.get("rol") != "admin":
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated


# ── login / logout ─────────────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = USUARIOS.get(username)
        if user and user["password"] == password:
            session["usuario"] = username
            session["rol"]     = user["rol"]
            return redirect(url_for("index"))
        else:
            error = "Usuario o contraseña incorrectos."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── index ──────────────────────────────────────────────────────────────────
@app.route("/")
@login_required
def index():
    return render_template("index.html",
                           usuario=session["usuario"],
                           rol=session["rol"])


# ── rutas ──────────────────────────────────────────────────────────────────
@app.route("/agregar_ruta", methods=["GET", "POST"])
@admin_required
def agregar_ruta():
    if request.method == "POST":
        # ── Corrección #6: validar campos vacíos antes de insertar ──
        nombre   = request.form.get("nombre", "").strip()
        zona     = request.form.get("zona", "").strip()
        horario  = request.form.get("horario", "").strip()
        colonias = request.form.get("colonias", "").strip()
        frecuencia = request.form.get("frecuencia", "").strip()
        distancia  = request.form.get("distancia", "").strip()

        if not all([nombre, zona, horario, colonias]):
            return render_template("agregar_ruta.html", error="Todos los campos son obligatorios.")

        nueva = {
            "nombre":    nombre,
            "zona":      zona,
            "horario":   horario,
            "colonias":  colonias,
            "frecuencia": frecuencia,   # #8 colonias y calles dentro de cada ruta
            "distancia":  distancia,
        }
        rutas.insert_one(nueva)
        return redirect(url_for("ver_rutas"))
    return render_template("agregar_ruta.html")


@app.route("/rutas")
@login_required
def ver_rutas():
    # ── Corrección #17: paginación en ver_rutas ──
    page  = int(request.args.get("page", 1))
    total = rutas.count_documents({})
    pages = max(1, -(-total // PER_PAGE))  # ceil
    skip  = (page - 1) * PER_PAGE
    lista = list(rutas.find().skip(skip).limit(PER_PAGE))
    return render_template("rutas.html",
                           rutas=lista,
                           rol=session["rol"],
                           usuario=session["usuario"],
                           page=page, pages=pages)


@app.route("/editar_ruta/<id>", methods=["GET", "POST"])
@admin_required
def editar_ruta(id):
    # ── Corrección #5: manejar InvalidId ──
    try:
        oid = ObjectId(id)
    except InvalidId:
        return redirect(url_for("ver_rutas"))

    ruta = rutas.find_one({"_id": oid})
    if not ruta:
        return redirect(url_for("ver_rutas"))

    if request.method == "POST":
        # ── Corrección #6: validar campos vacíos ──
        nombre   = request.form.get("nombre", "").strip()
        zona     = request.form.get("zona", "").strip()
        horario  = request.form.get("horario", "").strip()
        colonias = request.form.get("colonias", "").strip()
        frecuencia = request.form.get("frecuencia", "").strip()
        distancia  = request.form.get("distancia", "").strip()

        if not all([nombre, zona, horario, colonias]):
            return render_template("editar_ruta.html", ruta=ruta,
                                   error="Todos los campos son obligatorios.",
                                   usuario=session["usuario"], rol=session["rol"])

        datos = {
            "nombre":    nombre,
            "zona":      zona,
            "horario":   horario,
            "colonias":  colonias,
            "frecuencia": frecuencia,
            "distancia":  distancia,
        }
        rutas.update_one({"_id": oid}, {"$set": datos})
        return redirect(url_for("ver_rutas"))
    return render_template("editar_ruta.html", ruta=ruta,
                           usuario=session["usuario"], rol=session["rol"])


# ── Corrección #3: eliminar_ruta cambiado de GET a POST con confirmación ──
@app.route("/eliminar_ruta/<id>", methods=["POST"])
@admin_required
def eliminar_ruta(id):
    try:
        oid = ObjectId(id)
    except InvalidId:
        return redirect(url_for("ver_rutas"))
    rutas.delete_one({"_id": oid})
    return redirect(url_for("ver_rutas"))


# ── Corrección #16: buscar_ruta ampliado: filtrar por nombre y por colonia además de zona ──
@app.route("/buscar_ruta", methods=["GET", "POST"])
@login_required
def buscar_ruta():
    resultados = []
    mensaje = ""
    if request.method == "POST":
        valor = request.form.get("valor", "").strip()
        if valor:
            regex = {"$regex": valor, "$options": "i"}
            resultados = list(rutas.find({
                "$or": [
                    {"zona":     regex},
                    {"nombre":   regex},
                    {"colonias": regex},
                ]
            }))
        if not resultados:
            mensaje = "No se encontraron rutas con ese criterio."
    return render_template("buscar_ruta.html",
                           resultados=resultados,
                           mensaje=mensaje,
                           rol=session["rol"],
                           usuario=session["usuario"])


# ── reportes ───────────────────────────────────────────────────────────────
@app.route("/reportes")
@login_required
def ver_reportes():
    # ── Corrección #11: ciudadano solo ve sus propios reportes ──
    # ── Corrección #17: paginación en ver_reportes ──────────────
    page = int(request.args.get("page", 1))
    rol  = session.get("rol")
    usuario = session.get("usuario")

    filtro = {}
    if rol == "ciudadano":
        filtro = {"ciudadano.usuario": usuario}

    total = reportes.count_documents(filtro)
    pages = max(1, -(-total // PER_PAGE))
    skip  = (page - 1) * PER_PAGE
    lista = list(reportes.find(filtro).skip(skip).limit(PER_PAGE))

    return render_template("reportes.html",
                           reportes=lista,
                           rol=rol,
                           usuario=usuario,
                           page=page, pages=pages)


@app.route("/agregar_reporte", methods=["GET", "POST"])
@login_required
def agregar_reporte():
    if request.method == "POST":
        # ── Corrección #6: validar campos vacíos ──
        colonia     = request.form.get("colonia", "").strip()
        descripcion = request.form.get("descripcion", "").strip()
        fecha       = request.form.get("fecha", "").strip()
        nombre      = request.form.get("nombre", "").strip()
        telefono    = request.form.get("telefono", "").strip()

        if not all([colonia, descripcion, fecha, nombre, telefono]):
            return render_template("agregar_reporte.html",
                                   error="Todos los campos son obligatorios.",
                                   usuario=session["usuario"], rol=session["rol"])

        nuevo = {
            "colonia":     colonia,
            "descripcion": descripcion,
            "fecha":       fecha,
            "estado":      "pendiente",
            "ciudadano": {
                "nombre":   nombre,
                "telefono": telefono,
                "usuario":  session["usuario"],   # guardar quién reportó
            }
        }
        reportes.insert_one(nuevo)
        return redirect(url_for("ver_reportes"))
    return render_template("agregar_reporte.html",
                           usuario=session["usuario"], rol=session["rol"])


# ── Corrección #9: solo admin puede responder reportes ─────────────────────
# ── Corrección #10: vista de respuesta para que ciudadano la vea ───────────
@app.route("/responder_reporte/<id>", methods=["GET", "POST"])
@admin_required
def responder_reporte(id):
    try:
        oid = ObjectId(id)
    except InvalidId:
        return redirect(url_for("ver_reportes"))

    reporte = reportes.find_one({"_id": oid})
    if not reporte:
        return redirect(url_for("ver_reportes"))

    if request.method == "POST":
        respuesta = request.form.get("respuesta", "").strip()
        estado    = request.form.get("estado", "pendiente")
        reportes.update_one({"_id": oid}, {"$set": {
            "respuesta": respuesta,
            "estado":    estado
        }})
        return redirect(url_for("ver_reportes"))

    return render_template("responder_reporte.html",
                           reporte=reporte,
                           usuario=session["usuario"],
                           rol=session["rol"])


# ── Corrección #7: debug=False en producción ───────────────────────────────
if __name__ == "__main__":
    app.run(debug=False)
