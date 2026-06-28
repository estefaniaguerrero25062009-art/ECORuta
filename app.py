import os
import certifi
import base64
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

MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://gurn090625mmcrmla1_db_user:ecoruta123@cluster0.lqt9mjt.mongodb.net/ecoruta_nosql?retryWrites=true&w=majority")
client = MongoClient(MONGO_URI, server_api=ServerApi("1"), tlsCAFile=certifi.where(), tls=True)

db       = client["ecoruta_nosql"]
rutas    = db["rutas"]
reportes = db["reportes_ciudadanos"]

PER_PAGE = 5

USUARIOS = {
    "admin":     {"password": "ecoruta2026", "rol": "admin"},
    "ciudadano": {"password": "ecoruta2026", "rol": "ciudadano"}
}


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


@app.route("/")
@login_required
def index():
    return render_template("index.html",
                           usuario=session["usuario"],
                           rol=session["rol"])


@app.route("/agregar_ruta", methods=["GET", "POST"])
@admin_required
def agregar_ruta():
    if request.method == "POST":
        nombre     = request.form.get("nombre", "").strip()
        zona       = request.form.get("zona", "").strip()
        horario    = request.form.get("horario", "").strip()
        colonias   = request.form.get("colonias", "").strip()
        frecuencia = request.form.get("frecuencia", "").strip()
        distancia  = request.form.get("distancia", "").strip()

        if not all([nombre, zona, horario, colonias]):
            return render_template("agregar_ruta.html", error="Todos los campos son obligatorios.")

        rutas.insert_one({
            "nombre": nombre, "zona": zona, "horario": horario,
            "colonias": colonias, "frecuencia": frecuencia, "distancia": distancia,
        })
        return redirect(url_for("ver_rutas"))
    return render_template("agregar_ruta.html")


@app.route("/rutas")
@login_required
def ver_rutas():
    page  = int(request.args.get("page", 1))
    total = rutas.count_documents({})
    pages = max(1, -(-total // PER_PAGE))
    skip  = (page - 1) * PER_PAGE
    lista = list(rutas.find().skip(skip).limit(PER_PAGE))
    return render_template("rutas.html", rutas=lista, rol=session["rol"],
                           usuario=session["usuario"], page=page, pages=pages)


@app.route("/editar_ruta/<id>", methods=["GET", "POST"])
@admin_required
def editar_ruta(id):
    try:
        oid = ObjectId(id)
    except InvalidId:
        return redirect(url_for("ver_rutas"))

    ruta = rutas.find_one({"_id": oid})
    if not ruta:
        return redirect(url_for("ver_rutas"))

    if request.method == "POST":
        nombre     = request.form.get("nombre", "").strip()
        zona       = request.form.get("zona", "").strip()
        horario    = request.form.get("horario", "").strip()
        colonias   = request.form.get("colonias", "").strip()
        frecuencia = request.form.get("frecuencia", "").strip()
        distancia  = request.form.get("distancia", "").strip()

        if not all([nombre, zona, horario, colonias]):
            return render_template("editar_ruta.html", ruta=ruta,
                                   error="Todos los campos son obligatorios.",
                                   usuario=session["usuario"], rol=session["rol"])

        rutas.update_one({"_id": oid}, {"$set": {
            "nombre": nombre, "zona": zona, "horario": horario,
            "colonias": colonias, "frecuencia": frecuencia, "distancia": distancia,
        }})
        return redirect(url_for("ver_rutas"))
    return render_template("editar_ruta.html", ruta=ruta,
                           usuario=session["usuario"], rol=session["rol"])


@app.route("/eliminar_ruta/<id>", methods=["POST"])
@admin_required
def eliminar_ruta(id):
    try:
        oid = ObjectId(id)
    except InvalidId:
        return redirect(url_for("ver_rutas"))
    rutas.delete_one({"_id": oid})
    return redirect(url_for("ver_rutas"))


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
                "$or": [{"zona": regex}, {"nombre": regex}, {"colonias": regex}]
            }))
        if not resultados:
            mensaje = "No se encontraron rutas con ese criterio."
    return render_template("buscar_ruta.html", resultados=resultados,
                           mensaje=mensaje, rol=session["rol"],
                           usuario=session["usuario"])


@app.route("/reportes")
@login_required
def ver_reportes():
    page    = int(request.args.get("page", 1))
    rol     = session.get("rol")
    usuario = session.get("usuario")

    filtro = {}
    if rol == "ciudadano":
        filtro = {"ciudadano.usuario": usuario}

    total = reportes.count_documents(filtro)
    pages = max(1, -(-total // PER_PAGE))
    skip  = (page - 1) * PER_PAGE
    lista = list(reportes.find(filtro).skip(skip).limit(PER_PAGE))

    return render_template("reportes.html", reportes=lista, rol=rol,
                           usuario=usuario, page=page, pages=pages)


@app.route("/agregar_reporte", methods=["GET", "POST"])
@login_required
def agregar_reporte():
    if request.method == "POST":
        colonia     = request.form.get("colonia", "").strip()
        descripcion = request.form.get("descripcion", "").strip()
        fecha       = request.form.get("fecha", "").strip()
        nombre      = request.form.get("nombre", "").strip()
        telefono    = request.form.get("telefono", "").strip()

        if not all([colonia, descripcion, fecha, nombre, telefono]):
            return render_template("agregar_reporte.html",
                                   error="Todos los campos son obligatorios.",
                                   usuario=session["usuario"], rol=session["rol"])

        # Procesar imagen si se subió
        imagen_b64 = None
        imagen_tipo = None
        archivo = request.files.get("imagen")
        if archivo and archivo.filename != "":
            datos = archivo.read()
            if len(datos) > 2 * 1024 * 1024:  # límite 2MB
                return render_template("agregar_reporte.html",
                                       error="La imagen no debe superar 2MB.",
                                       usuario=session["usuario"], rol=session["rol"])
            imagen_b64  = base64.b64encode(datos).decode("utf-8")
            imagen_tipo = archivo.mimetype  # ej. image/jpeg

        nuevo = {
            "colonia": colonia, "descripcion": descripcion, "fecha": fecha,
            "estado": "pendiente",
            "ciudadano": {
                "nombre": nombre, "telefono": telefono,
                "usuario": session["usuario"],
            },
            "imagen":      imagen_b64,
            "imagen_tipo": imagen_tipo,
        }
        reportes.insert_one(nuevo)
        return redirect(url_for("ver_reportes"))
    return render_template("agregar_reporte.html",
                           usuario=session["usuario"], rol=session["rol"])


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
        reportes.update_one({"_id": oid}, {"$set": {
            "respuesta": request.form.get("respuesta", "").strip(),
            "estado":    request.form.get("estado", "pendiente")
        }})
        return redirect(url_for("ver_reportes"))

    return render_template("responder_reporte.html", reporte=reporte,
                           usuario=session["usuario"], rol=session["rol"])


@app.route("/eliminar_reporte/<id>", methods=["POST"])
@admin_required
def eliminar_reporte(id):
    try:
        oid = ObjectId(id)
    except InvalidId:
        return redirect(url_for("ver_reportes"))
    reportes.delete_one({"_id": oid})
    return redirect(url_for("ver_reportes"))


if __name__ == "__main__":
    app.run(debug=False)