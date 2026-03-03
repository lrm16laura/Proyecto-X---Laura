# ================================
# PROYECTO‑X — PARTE 1/8
# Login + Estilos + Sidebar + Navegación base
# ================================
import streamlit as st
import os

# ----------------
# 1) CONFIG PÁGINA
# ----------------
st.set_page_config(
    page_title="Proyecto‑X",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------
# 2) ESTILOS CSS
# ----------------
st.markdown("""
    <style>
        /* --- Botón por defecto (login) rojo --- */
        div.stButton > button {
            background-color: #FF4B4B;
            color: white;
            border-radius: 5px;
            font-weight: bold;
            width: 100%;
        }

        /* --- Sidebar azul corporativo --- */
        [data-testid="stSidebar"] {
            background-color: #004d85;
        }

        /* --- Logo / título en sidebar --- */
        .mosh-logo {
            color: white;
            font-size: 36px;
            font-weight: bold;
            text-align: center;
            margin-bottom: 20px;
        }

        /* --- Botones azul clarito para páginas internas --- */
        .btn-azul > button {
            background-color: #4da6ff !important;
            color: white !important;
            border-radius: 6px !important;
            font-weight: bold !important;
            width: 100% !important;
        }

        /* --- Contenedores de sección limpios --- */
        .section-container {
            background-color: #f8f9fa;
            padding: 1.0rem;
            border-radius: 10px;
            border-left: 5px solid #1f77b4;
            margin-bottom: 1.0rem;
        }

        /* --- Footer --- */
        .footer {
            text-align: center;
            color: #7f8c8d;
            font-size: 0.95rem;
            margin-top: 2rem;
            padding-top: 1rem;
            border-top: 1px solid #ecf0f1;
        }
    </style>
""", unsafe_allow_html=True)

# --------------------------------
# 3) ESTADO DE SESIÓN / CONSTANTES
# --------------------------------
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario" not in st.session_state:
    st.session_state.usuario = ""
if "current_page" not in st.session_state:
    # 👇 Tu flujo deseado:
    # - Cargas en “🗺️ Tablas maestras”
    # - Planificador en “🏭 Órdenes de fabricación”
    st.session_state.current_page = "Tablas maestras"

# Rutas y archivos (se usarán en partes siguientes)
UPLOAD_DIR = "archivos_cargados"
os.makedirs(UPLOAD_DIR, exist_ok=True)
HIST_PATH = os.path.join(UPLOAD_DIR, "historial_ejecuciones.xlsx")

# ----------------
# 4) PANTALLA LOGIN
# ----------------
if not st.session_state.autenticado:
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center; color: #004d85;'>💧 Proyecto‑X</h1>", unsafe_allow_html=True)
        st.subheader("Inicio de Sesión")

        usuario_input = st.text_input("Usuario:")
        password_input = st.text_input("Contraseña:", type="password")  # Simulación; sin validación real

        if st.button("Entrar"):
            if usuario_input.strip():
                st.session_state.autenticado = True
                st.session_state.usuario = usuario_input.strip()
                st.rerun()
            else:
                st.error("Por favor, introduce un nombre de usuario.")
    st.stop()  # No seguir si no está autenticado

# ----------------
# 5) SIDEBAR / MENÚ
# ----------------
with st.sidebar:
    st.markdown('<div class="mosh-logo">💧 Proyecto‑X</div>', unsafe_allow_html=True)

    def set_page(name: str):
        st.session_state.current_page = name

    # Orden y nombres según tu preferencia
    st.button("🗺️ Tablas maestras 〉", on_click=set_page, args=("Tablas maestras",))
    st.button("📋 Set Up Planning 〉", on_click=set_page, args=("Set Up Planning",))
    st.button("📦 Lanzamientos", on_click=set_page, args=("Lanzamientos",))
    st.button("🏭 Órdenes de fabricación 〉", on_click=set_page, args=("Órdenes de fabricación",))
    st.button("🔍 Consulta / Trazabilidad", on_click=set_page, args=("Consulta / Trazabilidad",))
    st.button("📜 Historial de ejecuciones", on_click=set_page, args=("Historial",))
    st.button("⚙️ Administración 〉", on_click=set_page, args=("Administración",))

    st.write("---")
    st.markdown(
        f"<p style='color:white;'>👤 Usuario: <b>{st.session_state.usuario}</b></p>",
        unsafe_allow_html=True
    )

    if st.button("🚫 Cerrar Sesión"):
        st.session_state.autenticado = False
        st.session_state.usuario = ""
        st.rerun()

# ----------------
# 6) CABECERA
# ----------------
head_col1, head_col2 = st.columns([10, 2])
with head_col1:
    st.write("≡")  # placeholder de menú superior
with head_col2:
    st.markdown(
        '<div style="color: #003366; font-size: 24px; font-weight: bold; text-align: right;">GRIFOLS</div>',
        unsafe_allow_html=True
    )

st.write("---")
st.write(f"## {st.session_state.current_page}")
st.write(f"Bienvenido al sistema, **{st.session_state.usuario}**.")

# ----------------
# 7) ROUTER DE PÁGINAS (placeholders por ahora)
#    El contenido real se añadirá en Partes 2..8
# ----------------
page = st.session_state.current_page

if page == "Tablas maestras":
    st.info("📥 Aquí irán las cargas de Excel (Capacidad, Materiales, Clientes, Demanda). "
            "Se añade en la **Parte 4**.")

elif page == "Set Up Planning":
    st.info("🛠️ Pantalla de Setup Planning (si la necesitáis).")

elif page == "Lanzamientos":
    st.info("📦 Pantalla de Lanzamientos (placeholder).")

elif page == "Órdenes de fabricación":
    st.info("🏭 Aquí se integrará **toda la planificación** (cálculo modo C, ajustes, gráficos). "
            "Se añade en la **Parte 6**.")

elif page == "Consulta / Trazabilidad":
    st.info("🔍 Pantalla de Consulta / Trazabilidad (placeholder).")

elif page == "Historial":
    st.info("📜 La **pantalla de historial** (tabla + descarga) llega en la **Parte 3**.")

elif page == "Administración":
    st.info("⚙️ Pantalla de Administración (placeholder).")

# Footer
st.markdown("---")
st.markdown("""
<div class="footer">
    <p>✨ <strong>Proyecto‑X</strong> — Marco base · Parte 1/8</p>
</div>
""", unsafe_allow_html=True)
# ================================
# PROYECTO‑X — PARTE 2/8
# Utilidades generales + Estado inicial de DataFrames
# ================================

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ----------------------------------------
# 1) ESTADO DE LOS DATAFRAMES PRINCIPALES
# ----------------------------------------
# (Se rellenan en Tablas maestras, Parte 4)

if "df_cap" not in st.session_state:
    st.session_state.df_cap = None
if "df_mat" not in st.session_state:
    st.session_state.df_mat = None
if "df_cli" not in st.session_state:
    st.session_state.df_cli = None
if "df_dem" not in st.session_state:
    st.session_state.df_dem = None

# ----------------------------------------
# 2) UTILIDADES GENERALES — LIMPIAS
# ----------------------------------------

def to_float_safe(v, default=0.0):
    """Convierte valores a float sin lanzar errores."""
    if pd.isna(v):
        return float(default)
    if isinstance(v, str):
        v = v.replace(",", ".").strip()
        if v == "":
            return float(default)
    try:
        return float(v)
    except:
        return float(default)

def norm_code(code):
    """Normaliza códigos de centro/material eliminando '.0' y rellenando ceros."""
    s = str(code).strip()
    if s.endswith(".0"):
        s = s[:-2]
    digits = "".join(ch for ch in s if ch.isdigit())
    if digits == "":
        return s
    if len(digits) < 4:
        digits = digits.zfill(4)
    return digits

def semana_iso_str_from_ts(ts: pd.Timestamp) -> str:
    """Devuelve semana ISO ('YYYY-Www')."""
    iso = ts.isocalendar()
    return f"{int(iso.year)}-W{int(iso.week):02d}"

def detectar_columna_cliente(df):
    """Detecta automáticamente la columna 'cliente' en cualquier idioma."""
    posibles = [
        "cliente","client","customer",
        "id cliente","codigo cliente","cod cliente",
        "cliente id","sap cliente"
    ]
    low = {c: c.lower().strip() for c in df.columns}
    for original, col_lower in low.items():
        for p in posibles:
            if p == col_lower or p in col_lower:
                return original
    return None

def guardar_archivo_subido(archivo, nombre_legible):
    """Guarda cualquier archivo excel que suba el usuario, con nombre entendible."""
    if archivo is None:
        return None

    t = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta = os.path.join(UPLOAD_DIR, f"{nombre_legible} {t}.xlsx")
    with open(ruta, "wb") as f:
        f.write(archivo.getbuffer())
    return ruta

# ----------------------------------------
# 3) MENSAJE DE TRAZABILIDAD (se puede quitar luego)
# ----------------------------------------
st.caption("🔧 Utilidades generales cargadas — Parte 2/8")
# ================================
# PROYECTO‑X — PARTE 3/8
# Módulo de HISTORIAL
# ================================

# ----------------------------------------
# Función principal: GUARDAR HISTORIAL
# ----------------------------------------
def guardar_historial(tipo, usuario, df_resultado, dg, mch):
    """
    Guarda un registro de ejecución del planificador.
    - tipo: 'Inicial' o 'Reajustado'
    - usuario: usuario logueado (string)
    - df_resultado: dataframe final generado por el cálculo
    - dg: código planta DG
    - mch: código planta MCH
    """

    if df_resultado is None or len(df_resultado) == 0:
        return None

    registro = pd.DataFrame([{
        "Fecha ejecución": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Usuario": usuario,
        "Tipo de ejecución": tipo,
        "Total propuestas": len(df_resultado),
        "Horas DG": df_resultado[df_resultado["Centro"] == dg]["Horas"].sum(),
        "Horas MCH": df_resultado[df_resultado["Centro"] == mch]["Horas"].sum()
    }])

    # Si existe historial, anexamos
    if os.path.exists(HIST_PATH):
        hist = pd.read_excel(HIST_PATH)
        hist = pd.concat([hist, registro], ignore_index=True)
    else:
        hist = registro

    hist.to_excel(HIST_PATH, index=False)
    return HIST_PATH

# ----------------------------------------
# Página del sidebar: MOSTRAR HISTORIAL
# ----------------------------------------
def mostrar_historial():
    """
    Página completa del historial:
    - Muestra tabla
    - Permite descargar
    - Diseñada para ser llamada desde el router (parte 1)
    """

    st.markdown("## 📜 Historial de ejecuciones")
    st.write("Historial de todas las ejecuciones de planificación realizadas en la aplicación.")

    if not os.path.exists(HIST_PATH):
        st.info("Todavía no existe ningún historial.")
        return

    df_hist = pd.read_excel(HIST_PATH)

    if df_hist.empty:
        st.info("No hay ejecuciones registradas aún.")
        return

    # Mostrar tabla
    st.dataframe(df_hist, use_container_width=True, height=350)

    # Botón de descarga con estilo "btn-azul"
    st.markdown('<div class="btn-azul">', unsafe_allow_html=True)
    with open(HIST_PATH, "rb") as f:
        st.download_button(
            "📥 Descargar historial",
            data=f,
            file_name="historial_ejecuciones.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="descargar_historial"
        )
    st.markdown('</div>', unsafe_allow_html=True)

# ----------------------------------------
# Mensaje de validación
# ----------------------------------------
st.caption("📜 Módulo de historial listo — Parte 3/8")
# ================================
# PROYECTO‑X — PARTE 4/8
# Página "Tablas maestras"
# Carga de los 4 Excel
# ================================

def pagina_tablas_maestras():
    """
    Página con la carga de Capacidad, Materiales, Clientes y Demanda.
    Se mostrará al seleccionar 'Tablas maestras' en el menú.
    """

    st.markdown("### 📥 Carga de archivos maestros")

    # -----------------------------
    # 1) CAPACIDAD
    # -----------------------------
    st.markdown('<div class="section-container">', unsafe_allow_html=True)
    st.markdown("#### 🏭 Capacidad de planta (Capacidad horas por Centro)")

    f1 = st.file_uploader("Subir archivo de Capacidad (.xlsx)", type=["xlsx"], key="cap")
    if f1:
        try:
            df_cap = pd.read_excel(f1)
            st.session_state.df_cap = df_cap.copy()

            guardar_archivo_subido(f1, "Capacidad")
            st.success("Archivo de capacidad cargado correctamente.")
            st.dataframe(df_cap, use_container_width=True)

        except Exception as e:
            st.error(f"Error al leer el archivo de capacidad: {e}")
    else:
        st.info("Sube el archivo de capacidad para continuar.")
    st.markdown('</div>', unsafe_allow_html=True)

    # -----------------------------
    # 2) MATERIALES
    # -----------------------------
    st.markdown('<div class="section-container">', unsafe_allow_html=True)
    st.markdown("#### 📦 Maestro de materiales")

    f2 = st.file_uploader("Subir archivo de Materiales (.xlsx)", type=["xlsx"], key="mat")
    if f2:
        try:
            df_mat = pd.read_excel(f2)
            st.session_state.df_mat = df_mat.copy()

            guardar_archivo_subido(f2, "Materiales")
            st.success("Archivo de materiales cargado correctamente.")
            st.dataframe(df_mat, use_container_width=True, height=350)

        except Exception as e:
            st.error(f"Error al leer el archivo de materiales: {e}")
    else:
        st.info("Sube el archivo de materiales para continuar.")
    st.markdown('</div>', unsafe_allow_html=True)

    # -----------------------------
    # 3) CLIENTES
    # -----------------------------
    st.markdown('<div class="section-container">', unsafe_allow_html=True)
    st.markdown("#### 👥 Maestro de clientes")

    f3 = st.file_uploader("Subir archivo de Clientes (.xlsx)", type=["xlsx"], key="cli")
    if f3:
        try:
            df_cli = pd.read_excel(f3)
            st.session_state.df_cli = df_cli.copy()

            guardar_archivo_subido(f3, "Clientes")
            st.success("Archivo de clientes cargado correctamente.")
            st.dataframe(df_cli, use_container_width=True, height=350)

        except Exception as e:
            st.error(f"Error al leer el archivo de clientes: {e}")
    else:
        st.info("Sube el archivo de clientes para continuar.")
    st.markdown('</div>', unsafe_allow_html=True)

    # -----------------------------
    # 4) DEMANDA
    # -----------------------------
    st.markdown('<div class="section-container">', unsafe_allow_html=True)
    st.markdown("#### 📈 Demanda (Fecha + Cantidad por Material)")

    f4 = st.file_uploader("Subir archivo de Demanda (.xlsx)", type=["xlsx"], key="dem")
    if f4:
        try:
            df_dem = pd.read_excel(f4)
            st.session_state.df_dem = df_dem.copy()

            guardar_archivo_subido(f4, "Demanda")
            st.success("Archivo de demanda cargado correctamente.")
            st.dataframe(df_dem, use_container_width=True, height=350)

        except Exception as e:
            st.error(f"Error al leer el archivo de demanda: {e}")
    else:
        st.info("Sube el archivo de demanda para continuar.")
    st.markdown('</div>', unsafe_allow_html=True)

    # -----------------------------
    # Validación final
    # -----------------------------
    if (st.session_state.df_cap is not None and
        st.session_state.df_mat is not None and
        st.session_state.df_cli is not None and
        st.session_state.df_dem is not None):

        st.success("✅ Todos los archivos han sido cargados correctamente.")
        st.info("Ya puedes ir a **🏭 Órdenes de fabricación** para ejecutar la planificación.")

    else:
        st.warning("⚠️ Faltan archivos por cargar.")

# ----------------------------------------
# Integración en el router (sustituye placeholder)
# ----------------------------------------
if page == "Tablas maestras":
    pagina_tablas_maestras()

# Aviso de carga correcta
st.caption("📥 Tablas maestras listas — Parte 4/8")
# ================================
# PROYECTO‑X — PARTE 5/8
# Módulo del PLANIFICADOR (refactorizado)
# ================================

# ----------------------------------------------------
# A) LECTURA Y PREPARACIÓN DE CAPACIDADES
# ----------------------------------------------------
def leer_capacidades(df_cap):
    """
    Lee el DataFrame de capacidades y devuelve un diccionario:
    { centro_normalizado : capacidad_en_horas }
    """
    if df_cap is None:
        st.error("No se cargó el archivo de capacidad.")
        return {}

    if "Centro" not in df_cap.columns:
        st.error("❌ Falta la columna 'Centro' en el archivo de capacidad.")
        return {}

    # Buscar la columna de capacidad
    col_lower = {c: c.lower().strip() for c in df_cap.columns}
    cap_col = None
    for c, low in col_lower.items():
        if "capacidad" in low and "hora" in low:
            cap_col = c
            break

    if cap_col is None:
        st.error("❌ No se encontró ninguna columna de capacidad de horas.")
        return {}

    capacidades = {}
    for _, row in df_cap.iterrows():
        centro = norm_code(row["Centro"])
        horas = to_float_safe(row[cap_col], 0)
        capacidades[centro] = horas

    return capacidades


def detectar_centros(capacidades: dict):
    """
    Detecta códigos DG y MCH automáticamente según sufijos conocidos.
    """
    if not capacidades:
        return None, None

    keys = list(capacidades.keys())

    DG = next((k for k in keys if k.endswith("833")), keys[0])
    MCH = next((k for k in keys if k.endswith("184")), keys[-1])

    return DG, MCH


# ----------------------------------------------------
# B) REPARTO PORCENTUAL POR SEMANAS
# ----------------------------------------------------
def repartir_porcentaje(df_semana, pct_dg, dg, mch):
    """
    Recibe un DF de una semana y asigna cada línea a DG o MCH
    según el porcentaje objetivo.
    """
    if pct_dg <= 0:
        df_semana["Centro"] = mch
        return df_semana

    if pct_dg >= 100:
        df_semana["Centro"] = dg
        return df_semana

    df_semana = df_semana.sort_values("Horas", ascending=False)
    total = df_semana["Horas"].sum()
    objetivo = total * (pct_dg / 100)

    acum = 0
    destinos = []
    for _, r in df_semana.iterrows():
        if acum < objetivo:
            destinos.append(dg)
            acum += r["Horas"]
        else:
            destinos.append(mch)

    df_semana["Centro"] = destinos
    return df_semana


# ----------------------------------------------------
# C) MODO C — PLANIFICACIÓN DIARIA CON LOTES
# ----------------------------------------------------
def modo_C(df_agr, df_mat, capacidades, DG_code, MCH_code):
    """
    Planificador Modo C refactorizado:
    - Respeta capacidad diaria
    - Divide por lotes mínimos/máximos
    - Desplaza producción al siguiente día si no cabe
    """
    # Obtener tiempos de ciclo
    tiempos = df_mat[[
        "Material", "Unidad",
        "Tiempo fabricación unidad DG",
        "Tiempo fabricación unidad MCH",
        "Tamaño lote mínimo",
        "Tamaño lote máximo"
    ]].drop_duplicates()

    df = df_agr.merge(tiempos, on=["Material", "Unidad"], how="left")

    # Capacidad remanente por (centro, día)
    capacidad_restante = {}

    def get_cap(centro, fecha):
        key = (centro, fecha)
        if key not in capacidad_restante:
            capacidad_restante[key] = capacidades.get(centro, 0)
        return capacidad_restante[key]

    def consume(centro, fecha, horas):
        capacidad_restante[(centro, fecha)] = max(
            0.0, get_cap(centro, fecha) - horas
        )

    def horas_necesarias(centro, qty, r):
        if centro == DG_code:
            tu = to_float_safe(r["Tiempo fabricación unidad DG"])
        else:
            tu = to_float_safe(r["Tiempo fabricación unidad MCH"])
        return qty * tu

    out = []
    propuesta_id = 1

    for _, r in df.iterrows():

        centro = norm_code(r["Centro"])
        fecha = pd.to_datetime(r["Fecha"]).normalize()
        semana = semana_iso_str_from_ts(fecha)

        cantidad = to_float_safe(r["Cantidad"], 0)
        lote_min = to_float_safe(r["Tamaño lote mínimo"], 0)
        lote_max = to_float_safe(r["Tamaño lote máximo"], 1)

        total = max(cantidad, lote_min)
        lote_max = max(lote_max, 1)

        # Partimos en bloques max
        partes = []
        pendiente = total
        while pendiente > 0:
            q = min(pendiente, lote_max)
            partes.append(round(q, 2))
            pendiente -= q

        # Programación diaria
        for ql in partes:
            p = ql
            while p > 0:
                cap = get_cap(centro, fecha)
                hnec = horas_necesarias(centro, p, r)

                if cap >= hnec:
                    # Cabe todo
                    consume(centro, fecha, hnec)
                    out.append({
                        "Nº de propuesta": propuesta_id,
                        "Material": r["Material"],
                        "Centro": centro,
                        "Clase de orden": "NORM",
                        "Cantidad a fabricar": round(p, 2),
                        "Unidad": r["Unidad"],
                        "Fecha": fecha.strftime("%d.%m.%Y"),
                        "Semana": semana
                    })
                    propuesta_id += 1
                    p = 0

                else:
                    # Parte que sí cabe
                    if cap > 0:
                        tu = (to_float_safe(r["Tiempo fabricación unidad DG"])
                              if centro == DG_code
                              else to_float_safe(r["Tiempo fabricación unidad MCH"]))
                        posible = cap / tu
                        posible = max(posible, 0)

                        consume(centro, fecha, cap)
                        out.append({
                            "Nº de propuesta": propuesta_id,
                            "Material": r["Material"],
                            "Centro": centro,
                            "Clase de orden": "NORM",
                            "Cantidad a fabricar": round(posible, 2),
                            "Unidad": r["Unidad"],
                            "Fecha": fecha.strftime("%d.%m.%Y"),
                            "Semana": semana
                        })
                        propuesta_id += 1
                        p -= posible

                    # Avanza al siguiente día
                    fecha += timedelta(days=1)
                    semana = semana_iso_str_from_ts(fecha)

    df_out = pd.DataFrame(out)

    # Recalcular horas finales
    tiempos = df_mat[[
        "Material", "Unidad",
        "Tiempo fabricación unidad DG",
        "Tiempo fabricación unidad MCH"
    ]].drop_duplicates()

    df_out = df_out.merge(tiempos, on=["Material", "Unidad"], how="left")
    df_out["Horas"] = np.where(
        df_out["Centro"] == DG_code,
        df_out["Cantidad a fabricar"] * df_out["Tiempo fabricación unidad DG"],
        df_out["Cantidad a fabricar"] * df_out["Tiempo fabricación unidad MCH"]
    )

    return df_out


# ----------------------------------------------------
# D) REPLANIFICACIÓN TRAS AJUSTES SEMANALES
# ----------------------------------------------------
def replanificar(df_base, df_mat, capacidades, DG_code, MCH_code, ajustes):
    """
    Aplica ajustes semanales mediante sliders y vuelve a ejecutar modo C.
    """
    df_repartido = []

    for sem in sorted(df_base["Semana"].astype(str).unique()):
        df_sem = df_base[df_base["Semana"].astype(str) == sem].copy()
        if df_sem.empty:
            continue

        pct = ajustes.get(sem, 50)
        df_sem = repartir_porcentaje(df_sem, pct, DG_code, MCH_code)
        df_repartido.append(df_sem)

    if not df_repartido:
        return df_base

    df_adj = pd.concat(df_repartido, ignore_index=True)

    # Modo C requiere columnas renombradas
    df_adj_pre = df_adj.rename(columns={"Cantidad a fabricar": "Cantidad"})[
        ["Material", "Unidad", "Centro", "Cantidad", "Fecha", "Semana"]
    ]

    return modo_C(df_adj_pre, df_mat, capacidades, DG_code, MCH_code)


# ----------------------------------------
# Marcar parte cargada
# ----------------------------------------
st.caption("🧠 Módulo del planificador cargado — Parte 5/8")
``
# ================================
# PROYECTO‑X — PARTE 6/8
# Página "Órdenes de fabricación"
# Planificador completo Modo C + Ajustes
# ================================

def pagina_ordenes_fabricacion():
    st.markdown("### 🏭 Planificación de Órdenes de Fabricación")

    # ===============================
    # Validar carga de maestros
    # ===============================
    if (st.session_state.df_cap is None or
        st.session_state.df_mat is None or
        st.session_state.df_cli is None or
        st.session_state.df_dem is None):

        st.warning("⚠️ Debes cargar los 4 archivos maestros en **🗺️ Tablas maestras** antes de continuar.")
        return

    df_cap = st.session_state.df_cap
    df_mat = st.session_state.df_mat
    df_cli = st.session_state.df_cli
    df_dem = st.session_state.df_dem

    # ===============================
    # PREPARAR DATOS DEMANDA
    # ===============================
    df_dem = df_dem.copy()
    df_dem["Fecha_DT"] = pd.to_datetime(df_dem["Fecha de necesidad"])
    iso = df_dem["Fecha_DT"].dt.isocalendar()
    df_dem["Semana_Label"] = iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)

    # ===============================
    # DETECTAR COLUMNAS DE CLIENTE
    # ===============================
    col_cli_dem = detectar_columna_cliente(df_dem)
    col_cli_cli = detectar_columna_cliente(df_cli)

    if not col_cli_dem or not col_cli_cli:
        st.error("❌ No se encontró una columna de cliente en Demanda o en Clientes.")
        return

    # ===============================
    # MERGE DE DEMANDA + MATERIALES + CLIENTES
    # ===============================
    df = df_dem.merge(df_mat, on=["Material", "Unidad"], how="left")
    df = df.merge(df_cli, left_on=col_cli_dem, right_on=col_cli_cli, how="left")

    # ===============================
    # DETECCIÓN DE CENTRO POR COSTE
    # ===============================
    COL_COST_DG = next((c for c in df.columns if "dg" in c.lower() and "cost" in c.lower()), None)
    COL_COST_MCH = next((c for c in df.columns if "mch" in c.lower() and "cost" in c.lower()), None)

    def decidir_centro(r):
        c1 = to_float_safe(r.get(COL_COST_DG, 0))
        c2 = to_float_safe(r.get(COL_COST_MCH, 0))
        return DG if c1 < c2 else MCH

    # ===============================
    # CÁLCULO DE CAPACIDADES
    # ===============================
    capacidades = leer_capacidades(df_cap)
    DG, MCH = detectar_centros(capacidades)

    # ===============================
    # ASIGNACIÓN CENTROS BASE SEGÚN COSTE
    # ===============================
    df["Centro_Base"] = df.apply(decidir_centro, axis=1)

    # ===============================
    # AGRUPACIÓN BASE PARA MODO C
    # ===============================
    g = df.groupby(
        ["Material", "Unidad", "Centro_Base", "Fecha de necesidad", "Semana_Label"],
        dropna=False
    ).agg({
        "Cantidad": "sum",
        "Tamaño lote mínimo": "first",
        "Tamaño lote máximo": "first"
    }).reset_index()

    g = g.rename(columns={
        "Centro_Base": "Centro",
        "Fecha de necesidad": "Fecha",
        "Semana_Label": "Semana"
    })

    # ===============================
    # BOTÓN EJECUCIÓN CÁLCULO INICIAL
    # ===============================
    st.markdown("#### 🚀 Ejecutar cálculo inicial")
    ejecutar = st.button("⚙️ Ejecutar planificación", use_container_width=True)

    if ejecutar:
        with st.spinner("Generando planificación inicial..."):

            g["Lote_min"] = g["Tamaño lote mínimo"]
            g["Lote_max"] = g["Tamaño lote máximo"]
            g["Centro"] = g["Centro"].apply(norm_code)

            df_base = modo_C(
                df_agr=g[["Material", "Unidad", "Centro", "Cantidad", "Fecha", "Semana"]],
                df_mat=df_mat,
                capacidades=capacidades,
                DG_code=DG,
                MCH_code=MCH
            )

            # Guardar en sesión
            st.session_state.df_base = df_base
            st.session_state.capacidades_calc = capacidades
            st.session_state.DG_calc = DG
            st.session_state.MCH_calc = MCH

        st.success("✅ Cálculo inicial completado.")

        # Guardar historial
        guardar_historial("Inicial", st.session_state.usuario, df_base, DG, MCH)
        st.info("📜 Historial actualizado.")

    # ===============================
    # MOSTRAR RESULTADOS DEL CÁLCULO
    # ===============================
    if "df_base" in st.session_state and st.session_state.df_base is not None:
        df_base = st.session_state.df_base
        DG = st.session_state.DG_calc
        MCH = st.session_state.MCH_calc

        st.markdown("---")
        st.markdown("### 📊 Resultados de la planificación inicial")

        # Métricas principales
        cols = st.columns(3)
        cols[0].metric("Total propuestas", f"{len(df_base):,}".replace(",", "."))
        cols[1].metric(f"Horas totales {DG}", f"{df_base[df_base['Centro']==DG]['Horas'].sum():,.1f}h".replace(",", "."))
        cols[2].metric(f"Horas totales {MCH}", f"{df_base[df_base['Centro']==MCH]['Horas'].sum():,.1f}h".replace(",", "."))

        # ===============================
        # GRÁFICO SEMANAL
        # ===============================
        st.markdown("#### 📅 Gráfico semanal de carga")

        df_plot = df_base.copy()
        df_plot["Semana"] = df_plot["Semana"].astype(str)
        df_plot["Centro"] = df_plot["Centro"].astype(str)

        carga_plot = (
            df_plot.groupby(["Semana", "Centro"])["Horas"]
            .sum().unstack().fillna(0).sort_index()
        )

        st.bar_chart(carga_plot, use_container_width=True)
        st.dataframe(carga_plot.style.format("{:,.1f}"), use_container_width=True)

        # ===============================
        # DETALLE PROPUESTAS + DESCARGA
        # ===============================
        st.markdown("#### 📋 Detalle de propuestas")
        st.dataframe(df_base, use_container_width=True)

        with st.expander("📥 Descargar Excel"):
            ruta_xlsx = os.path.join(UPLOAD_DIR, f"Propuesta Inicial {datetime.now().strftime('%Y%m%d')}.xlsx")
            df_base.to_excel(ruta_xlsx, index=False)
            with open(ruta_xlsx, "rb") as f:
                st.download_button("Descargar Excel", f, file_name="Propuesta_Inicial.xlsx")

        # ===============================
        # REAJUSTE SEMANAL (sliders)
        # ===============================
        st.markdown("---")
        st.markdown("### 🎛️ Ajuste por semana (DG vs MCH)")
        st.info("0% = todo a MCH · 100% = todo a DG")

        semanas = sorted(df_base["Semana"].astype(str).unique())
        ajustes = {}

        cols = st.columns(4)
        for i, sem in enumerate(semanas):
            with cols[i % 4]:
                ajustes[sem] = st.slider(f"Semana {sem}", 0, 100, 50)

        aplicar = st.button("🔁 Aplicar ajustes y replanificar", use_container_width=True)

        if aplicar:
            with st.spinner("Replanificando..."):

                df_final = replanificar(
                    df_base=df_base,
                    df_mat=df_mat,
                    capacidades=capacidades,
                    DG_code=DG,
                    MCH_code=MCH,
                    ajustes=ajustes
                )

                st.session_state.df_replan = df_final

            # Guardar historial
            guardar_historial("Reajustado", st.session_state.usuario, df_final, DG, MCH)

            st.success("🔄 Replanificación completada.")
            st.info("📜 Historial actualizado.")

    # ===============================
    # MOSTRAR RESULTADOS REPLANIFICADOS
    # ===============================
    if "df_replan" in st.session_state and st.session_state.df_replan is not None:
        df_final = st.session_state.df_replan

        st.markdown("---")
        st.markdown("### 📈 Resultados tras replanificación")

        cols = st.columns(3)
        cols[0].metric("Total propuestas", f"{len(df_final):,}".replace(",", "."))
        cols[1].metric(f"Horas {DG}", f"{df_final[df_final['Centro']==DG]['Horas'].sum():,.1f}h".replace(",", "."))
        cols[2].metric(f"Horas {MCH}", f"{df_final[df_final['Centro']==MCH]['Horas'].sum():,.1f}h".replace(",", "."))

        st.markdown("#### 📅 Gráfico semanal replanificado")

        dfp = df_final.copy()
        dfp["Semana"] = dfp["Semana"].astype(str)
        dfp["Centro"] = dfp["Centro"].astype(str)

        carga_plot2 = (
            dfp.groupby(["Semana", "Centro"])["Horas"]
            .sum().unstack().fillna(0).sort_index()
        )

        st.bar_chart(carga_plot2, use_container_width=True)
        st.dataframe(carga_plot2.style.format("{:,.1f}"), use_container_width=True)

        # Detalle
        st.markdown("#### 📋 Detalle final")
        st.dataframe(df_final, use_container_width=True)

        ruta_fin = os.path.join(UPLOAD_DIR, f"Propuesta Replanificada {datetime.now().strftime('%Y%m%d')}.xlsx")
        df_final.to_excel(ruta_fin, index=False)

        with st.expander("📥 Descargar Excel"):
            with open(ruta_fin, "rb") as f:
                st.download_button("Descargar Excel", f, file_name="Propuesta_Replanificada.xlsx")

# ----------------------------------------
# Insertar en router
# ----------------------------------------
if page == "Órdenes de fabricación":
    pagina_ordenes_fabricacion()

st.caption("🏭 Página de planificación lista — Parte 6/8")
# ================================
# PROYECTO‑X — PARTE 7/8
# Validadores + Mensajes UX + Limpieza de estado
# ================================

# ----------------------------------------------------
# VALIDAR COLUMNAS OBLIGATORIAS
# ----------------------------------------------------
def validar_columnas_obligatorias(df, columnas, nombre_df):
    """
    Valida que un DataFrame tenga las columnas indicadas.
    Si falta alguna, muestra un error elegante.
    """
    faltan = [c for c in columnas if c not in df.columns]
    if faltan:
        st.error(f"""
        ❌ El archivo **{nombre_df}** no contiene todas las columnas obligatorias.
        
        Columnas requeridas:
        - {", ".join(columnas)}

        Columnas faltantes:
        - {", ".join(faltan)}
        """)
        return False
    
    return True


# ----------------------------------------------------
# LIMPIAR RESULTADOS DE PLANIFICACIÓN
# ----------------------------------------------------
def limpiar_estado_planificacion():
    """
    Se llama cada vez que se vuelven a cargar excels en 'Tablas maestras'.
    Evita que el usuario use datos antiguos mezclados.
    """
    if "df_base" in st.session_state:
        del st.session_state["df_base"]
    if "df_replan" in st.session_state:
        del st.session_state["df_replan"]
    if "capacidades_calc" in st.session_state:
        del st.session_state["capacidades_calc"]
    if "DG_calc" in st.session_state:
        del st.session_state["DG_calc"]
    if "MCH_calc" in st.session_state:
        del st.session_state["MCH_calc"]

    st.info("ℹ️ Se han limpiado los resultados anteriores para evitar inconsistencias.")


# ----------------------------------------------------
# FEEDBACK DE EXCEL SUBIDO
# ----------------------------------------------------
def mostrar_ok_archivo(nombre):
    st.markdown(
        f"""
        <div style='background:#e8f7e4;border-left:6px solid #4CAF50;padding:10px;margin-top:5px;border-radius:5px;'>
            <b>✔ Archivo {nombre} cargado correctamente</b>
        </div>
        """,
        unsafe_allow_html=True
    )


# ----------------------------------------------------
# Mensaje de confirmación de módulo cargado
# ----------------------------------------------------
st.caption("🛡️ Validadores UX listos — Parte 7/8")
# ================================
# PROYECTO‑X — PARTE 8/8
# Integración final del router + Footer definitivo
# ================================

# ----------------------------------------
# 1) Router definitivo de páginas
#    (Sustituye los placeholders)
# ----------------------------------------
if page == "Tablas maestras":
    pagina_tablas_maestras()

elif page == "Set Up Planning":
    st.info("🛠️ Esta pantalla está disponible para futuras funciones. (Vacío por ahora)")

elif page == "Lanzamientos":
    st.info("📦 Pantalla de lanzamientos (pendiente de definir).")

elif page == "Órdenes de fabricación":
    pagina_ordenes_fabricacion()

elif page == "Consulta / Trazabilidad":
    st.info("🔍 Pantalla de consulta / trazabilidad (pendiente de definir).")

elif page == "Historial de ejecuciones" or page == "Historial":
    mostrar_historial()

elif page == "Administración":
    st.info("⚙️ Pantalla de administración (pendiente de configuración).")

# ----------------------------------------
# 2) Footer corporativo final
# ----------------------------------------
st.markdown("---")
st.markdown(
    """
    <div class="footer">
        <p>💧 <strong>Proyecto‑X</strong> — Sistema de planificación completo<br>
        Desarrollado e integrado para uso interno.</p>
    </div>
    """,
    unsafe_allow_html=True
)

# Marcar completado
st.caption("🎉 Proyecto‑X completamente configurado — Parte 8/8")
