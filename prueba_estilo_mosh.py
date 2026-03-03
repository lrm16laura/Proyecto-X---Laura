import streamlit as st
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

# ================================
# PROYECTO‑X — BLOQUE 1/4
# Login + Estilos + Sidebar + Estado + Utilidades
# ================================

# ---------- CONFIGURACIÓN ----------
st.set_page_config(
    page_title="Proyecto‑X",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- ESTILOS CSS ----------
st.markdown("""
<style>
/* Botón login rojo */
div.stButton > button {
    background-color: #FF4B4B;
    color: white;
    border-radius: 5px;
    font-weight: bold;
    width: 100%;
}

/* Sidebar azul oscuro corporativo */
[data-testid="stSidebar"] {
    background-color: #004d85;
}

/* Logo vertical */
.mosh-logo {
    color: white;
    font-size: 36px;
    font-weight: bold;
    text-align: center;
    margin-bottom: 20px;
}

/* Botón interno azul clarito */
.btn-azul > button {
    background-color: #4da6ff !important;
    color: white !important;
    border-radius: 6px !important;
    font-weight: bold !important;
    width: 100% !important;
}

/* Contenedores de sección */
.section-container {
    background-color: #f8f9fa;
    padding: 1rem;
    border-radius: 10px;
    border-left: 5px solid #1f77b4;
    margin-bottom: 1rem;
}

/* Footer */
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

# ---------- ESTADO DE SESIÓN ----------
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if "usuario" not in st.session_state:
    st.session_state.usuario = ""

if "current_page" not in st.session_state:
    st.session_state.current_page = "Tablas maestras"

if "df_cap" not in st.session_state:
    st.session_state.df_cap = None
if "df_mat" not in st.session_state:
    st.session_state.df_mat = None
if "df_cli" not in st.session_state:
    st.session_state.df_cli = None
if "df_dem" not in st.session_state:
    st.session_state.df_dem = None

UPLOAD_DIR = "archivos_cargados"
os.makedirs(UPLOAD_DIR, exist_ok=True)

HIST_PATH = os.path.join(UPLOAD_DIR, "historial_ejecuciones.xlsx")

# ---------- LOGIN ----------
if not st.session_state.autenticado:
    col1, col2, col3 = st.columns([1,1,1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align:center;color:#004d85;'>💧 Proyecto‑X</h1>", unsafe_allow_html=True)
        st.subheader("Inicio de sesión")

        usuario_input = st.text_input("Usuario:")
        password_input = st.text_input("Contraseña:", type="password")

        if st.button("Entrar"):
            if usuario_input.strip():
                st.session_state.autenticado = True
                st.session_state.usuario = usuario_input.strip()
                st.rerun()
            else:
                st.error("Introduce un usuario válido.")
    st.stop()

# ---------- SIDEBAR ----------
with st.sidebar:
    st.markdown('<div class="mosh-logo">💧 Proyecto‑X</div>', unsafe_allow_html=True)

    def set_page(name):
        st.session_state.current_page = name

    st.button("🗺️ Tablas maestras 〉", on_click=set_page, args=("Tablas maestras",))
    st.button("📋 Set Up Planning 〉", on_click=set_page, args=("Set Up Planning",))
    st.button("📦 Lanzamientos", on_click=set_page, args=("Lanzamientos",))
    st.button("🏭 Órdenes de fabricación 〉", on_click=set_page, args=("Órdenes de fabricación",))
    st.button("🔍 Consulta / Trazabilidad", on_click=set_page, args=("Consulta / Trazabilidad",))
    st.button("📜 Historial de ejecuciones", on_click=set_page, args=("Historial",))
    st.button("⚙️ Administración 〉", on_click=set_page, args=("Administración",))

    st.write("---")
    st.markdown(f"<p style='color:white;'>👤 Usuario: <b>{st.session_state.usuario}</b></p>", unsafe_allow_html=True)
    if st.button("🚫 Cerrar sesión"):
        st.session_state.autenticado = False
        st.session_state.usuario = ""
        st.rerun()

# ---------- CABECERA ----------
c1, c2 = st.columns([10,2])
with c1:
    st.write("≡")
with c2:
    st.markdown("<div style='font-size:24px;font-weight:bold;color:#003366;text-align:right;'>GRIFOLS</div>", unsafe_allow_html=True)

st.write("---")
st.write(f"## {st.session_state.current_page}")
st.write(f"Bienvenido, **{st.session_state.usuario}**.")

page = st.session_state.current_page

# ---------- UTILIDADES GENERALES ----------
def to_float_safe(v, default=0.0):
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
    s = str(code).strip()
    if s.endswith(".0"):
        s = s[:-2]
    digits = "".join(ch for ch in s if ch.isdigit())
    if digits == "":
        return s
    return digits.zfill(4) if len(digits) < 4 else digits

def semana_iso_str_from_ts(ts: pd.Timestamp) -> str:
    iso = ts.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"

def detectar_columna_cliente(df):
    posibles = [
        "cliente", "client", "customer",
        "id cliente", "codigo cliente", "cod cliente",
        "cliente id", "sap cliente"
    ]
    lc = {c: c.lower().strip() for c in df.columns}
    for orig, low in lc.items():
        for p in posibles:
            if p == low or p in low:
                return orig
    return None

def guardar_archivo_subido(archivo, nombre_legible):
    t = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta = os.path.join(UPLOAD_DIR, f"{nombre_legible} {t}.xlsx")
    with open(ruta, "wb") as f:
        f.write(archivo.getbuffer())
    return ruta
# ================================
# PROYECTO‑X — BLOQUE 2/4
# Página "Tablas maestras"
# ================================

def limpiar_estado_planificacion():
    """Evita que se mezclen cálculos antiguos con datos nuevos."""
    for key in ["df_base", "df_replan", "capacidades_calc", "DG_calc", "MCH_calc"]:
        if key in st.session_state:
            del st.session_state[key]


def pagina_tablas_maestras():
    st.markdown("### 📥 Carga de archivos maestros")

    # ============================================================
    # 1) CAPACIDAD
    # ============================================================
    st.markdown('<div class="section-container">', unsafe_allow_html=True)
    st.markdown("#### 🏭 Capacidad de planta (Capacidad horas por Centro)")

    f1 = st.file_uploader("Subir archivo de Capacidad (.xlsx)", type=["xlsx"], key="cap")

    if f1:
        try:
            df_cap = pd.read_excel(f1)
            st.session_state.df_cap = df_cap.copy()
            limpiar_estado_planificacion()
            guardar_archivo_subido(f1, "Capacidad")
            st.success("✔ Archivo de capacidad cargado correctamente.")
            st.dataframe(df_cap, use_container_width=True)
        except Exception as e:
            st.error(f"❌ Error al leer el archivo de capacidad: {e}")
    else:
        st.info("Sube el archivo de capacidad para continuar.")
    st.markdown('</div>', unsafe_allow_html=True)

    # ============================================================
    # 2) MATERIALES
    # ============================================================
    st.markdown('<div class="section-container">', unsafe_allow_html=True)
    st.markdown("#### 📦 Maestro de materiales")

    f2 = st.file_uploader("Subir archivo de Materiales (.xlsx)", type=["xlsx"], key="mat")

    if f2:
        try:
            df_mat = pd.read_excel(f2)
            st.session_state.df_mat = df_mat.copy()
            limpiar_estado_planificacion()
            guardar_archivo_subido(f2, "Materiales")
            st.success("✔ Archivo de materiales cargado correctamente.")
            st.dataframe(df_mat, use_container_width=True, height=350)
        except Exception as e:
            st.error(f"❌ Error al leer el archivo de materiales: {e}")
    else:
        st.info("Sube el archivo de materiales para continuar.")
    st.markdown('</div>', unsafe_allow_html=True)

    # ============================================================
    # 3) CLIENTES
    # ============================================================
    st.markdown('<div class="section-container">', unsafe_allow_html=True)
    st.markdown("#### 👥 Maestro de clientes")

    f3 = st.file_uploader("Subir archivo de Clientes (.xlsx)", type=["xlsx"], key="cli")

    if f3:
        try:
            df_cli = pd.read_excel(f3)
            st.session_state.df_cli = df_cli.copy()
            limpiar_estado_planificacion()
            guardar_archivo_subido(f3, "Clientes")
            st.success("✔ Archivo de clientes cargado correctamente.")
            st.dataframe(df_cli, use_container_width=True, height=350)
        except Exception as e:
            st.error(f"❌ Error al leer el archivo de clientes: {e}")
    else:
        st.info("Sube el archivo de clientes para continuar.")
    st.markdown('</div>', unsafe_allow_html=True)

    # ============================================================
    # 4) DEMANDA
    # ============================================================
    st.markdown('<div class="section-container">', unsafe_allow_html=True)
    st.markdown("#### 📈 Demanda (Fecha + Cantidad por Material)")

    f4 = st.file_uploader("Subir archivo de Demanda (.xlsx)", type=["xlsx"], key="dem")

    if f4:
        try:
            df_dem = pd.read_excel(f4)
            st.session_state.df_dem = df_dem.copy()
            limpiar_estado_planificacion()
            guardar_archivo_subido(f4, "Demanda")
            st.success("✔ Archivo de demanda cargado correctamente.")
            st.dataframe(df_dem, use_container_width=True, height=350)
        except Exception as e:
            st.error(f"❌ Error al leer el archivo de demanda: {e}")
    else:
        st.info("Sube el archivo de demanda para continuar.")
    st.markdown('</div>', unsafe_allow_html=True)

    # ============================================================
    # VALIDACIÓN GLOBAL
    # ============================================================
    if all([
        st.session_state.df_cap is not None,
        st.session_state.df_mat is not None,
        st.session_state.df_cli is not None,
        st.session_state.df_dem is not None
    ]):
        st.success("🎉 ¡Todos los archivos han sido cargados correctamente!")
        st.info("Ahora puedes ir a 👉 **🏭 Órdenes de fabricación** para ejecutar la planificación.")
    else:
        st.warning("⚠️ Aún faltan archivos por cargar.")


# ---------- INTEGRACIÓN EN EL ROUTER ----------
if page == "Tablas maestras":
    pagina_tablas_maestras()
# ================================
# PROYECTO‑X — BLOQUE 3/4
# PLANIFICADOR COMPLETO + REPLANIFICACIÓN + HISTORIAL
# ================================

# ----------------------------------------------------
# A) CAPACIDADES
# ----------------------------------------------------
def leer_capacidades(df_cap):
    """Devuelve un diccionario {centro: capacidad_horas}."""
    if df_cap is None:
        st.error("No se cargó el archivo de capacidad.")
        return {}

    if "Centro" not in df_cap.columns:
        st.error("❌ Falta la columna 'Centro' en Capacidad.")
        return {}

    # Buscar columna de capacidad
    col_lower = {c: c.lower().strip() for c in df_cap.columns}
    cap_col = None
    for c, lower in col_lower.items():
        if "capacidad" in lower and "hora" in lower:
            cap_col = c
            break

    if not cap_col:
        st.error("❌ No se encuentra una columna de capacidad en horas.")
        return {}

    capacidades = {}
    for _, r in df_cap.iterrows():
        centro = norm_code(r["Centro"])
        horas = to_float_safe(r[cap_col], 0)
        capacidades[centro] = horas

    return capacidades


def detectar_centros(capacidades):
    """Detecta DG y MCH por sufijos conocidos."""
    if not capacidades:
        return None, None
    keys = list(capacidades.keys())
    DG = next((k for k in keys if k.endswith("833")), keys[0])
    MCH = next((k for k in keys if k.endswith("184")), keys[-1])
    return DG, MCH


# ----------------------------------------------------
# B) REPARTO PORCENTUAL
# ----------------------------------------------------
def repartir_porcentaje(df_semana, pct_dg, dg, mch):
    """Reparte la carga semanal según % DG vs MCH."""
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
# C) MODO C – Planificador completo
# ----------------------------------------------------
def modo_C(df_agr, df_mat, capacidades, DG_code, MCH_code):
    """Planificador con lotes + capacidad diaria."""
    tiempos = df_mat[[
        "Material", "Unidad",
        "Tiempo fabricación unidad DG",
        "Tiempo fabricación unidad MCH",
        "Tamaño lote mínimo",
        "Tamaño lote máximo"
    ]].drop_duplicates()

    df = df_agr.merge(tiempos, on=["Material", "Unidad"], how="left")

    capacidad_restante = {}  # (centro, fecha) → horas disponibles

    def cap_rest(centro, fecha):
        key = (centro, fecha)
        if key not in capacidad_restante:
            capacidad_restante[key] = capacidades.get(centro, 0)
        return capacidad_restante[key]

    def consumir(centro, fecha, horas):
        capacidad_restante[(centro, fecha)] = max(0, cap_rest(centro, fecha) - horas)

    def horas_necesarias(centro, cantidad, fila):
        if centro == DG_code:
            tu = to_float_safe(fila["Tiempo fabricación unidad DG"])
        else:
            tu = to_float_safe(fila["Tiempo fabricación unidad MCH"])
        return cantidad * tu

    out = []
    proposal_id = 1

    for _, fila in df.iterrows():

        centro = norm_code(fila["Centro"])
        fecha = pd.to_datetime(fila["Fecha"]).normalize()
        semana = semana_iso_str_from_ts(fecha)

        cantidad = to_float_safe(fila["Cantidad"])
        lote_min = to_float_safe(fila["Tamaño lote mínimo"])
        lote_max = to_float_safe(fila["Tamaño lote máximo"], 1)
        cantidad = max(cantidad, lote_min)

        # Dividir en lotes
        partes = []
        pendiente = cantidad
        while pendiente > 0:
            q = min(pendiente, lote_max)
            partes.append(round(q, 2))
            pendiente -= q

        for qty in partes:
            restante = qty
            while restante > 0:
                cap = cap_rest(centro, fecha)
                hnec = horas_necesarias(centro, restante, fila)

                if cap >= hnec:
                    # Cabe entero
                    consumir(centro, fecha, hnec)
                    out.append({
                        "Nº de propuesta": proposal_id,
                        "Material": fila["Material"],
                        "Centro": centro,
                        "Clase de orden": "NORM",
                        "Cantidad a fabricar": round(restante, 2),
                        "Unidad": fila["Unidad"],
                        "Fecha": fecha.strftime("%d.%m.%Y"),
                        "Semana": semana
                    })
                    proposal_id += 1
                    restante = 0

                else:
                    # Solo cabe una parte
                    if cap > 0:
                        tu = (to_float_safe(fila["Tiempo fabricación unidad DG"])
                              if centro == DG_code
                              else to_float_safe(fila["Tiempo fabricación unidad MCH"]))
                        posible = cap / tu
                        posible = max(posible, 0)

                        consumir(centro, fecha, cap)
                        out.append({
                            "Nº de propuesta": proposal_id,
                            "Material": fila["Material"],
                            "Centro": centro,
                            "Clase de orden": "NORM",
                            "Cantidad a fabricar": round(posible, 2),
                            "Unidad": fila["Unidad"],
                            "Fecha": fecha.strftime("%d.%m.%Y"),
                            "Semana": semana
                        })
                        proposal_id += 1
                        restante -= posible

                    fecha += timedelta(days=1)
                    semana = semana_iso_str_from_ts(fecha)

    df_out = pd.DataFrame(out)

    # Recalcular horas
    tiempos2 = df_mat[[
        "Material", "Unidad",
        "Tiempo fabricación unidad DG",
        "Tiempo fabricación unidad MCH"
    ]].drop_duplicates()

    df_out = df_out.merge(tiempos2, on=["Material", "Unidad"], how="left")

    df_out["Horas"] = np.where(
        df_out["Centro"] == DG_code,
        df_out["Cantidad a fabricar"] * df_out["Tiempo fabricación unidad DG"],
        df_out["Cantidad a fabricar"] * df_out["Tiempo fabricación unidad MCH"]
    )

    return df_out


# ----------------------------------------------------
# D) REPLANIFICACIÓN COMPLETA
# ----------------------------------------------------
def replanificar(df_base, df_mat, capacidades, DG_code, MCH_code, ajustes):
    df_sem_list = []

    for semana in sorted(df_base["Semana"].astype(str).unique()):
        df_s = df_base[df_base["Semana"].astype(str) == semana].copy()
        pct = ajustes.get(semana, 50)
        df_s = repartir_porcentaje(df_s, pct, DG_code, MCH_code)
        df_sem_list.append(df_s)

    df_adj = pd.concat(df_sem_list, ignore_index=True)

    df_adj_pre = df_adj.rename(columns={"Cantidad a fabricar": "Cantidad"})[
        ["Material", "Unidad", "Centro", "Cantidad", "Fecha", "Semana"]
    ]

    return modo_C(df_adj_pre, df_mat, capacidades, DG_code, MCH_code)


# ----------------------------------------------------
# E) PÁGINA COMPLETA: ÓRDENES DE FABRICACIÓN
# ----------------------------------------------------
def pagina_ordenes_fabricacion():

    st.markdown("### 🏭 Planificación de Órdenes de Fabricación")

    # Validar cargas
    if not all([
        st.session_state.df_cap is not None,
        st.session_state.df_mat is not None,
        st.session_state.df_cli is not None,
        st.session_state.df_dem is not None
    ]):
        st.warning("⚠️ Primero debes cargar todos los maestros en '🗺️ Tablas maestras'.")
        return

    df_cap = st.session_state.df_cap
    df_mat = st.session_state.df_mat
    df_cli = st.session_state.df_cli
    df_dem = st.session_state.df_dem

    # DEMANDA
    df_dem = df_dem.copy()
    df_dem["Fecha_DT"] = pd.to_datetime(df_dem["Fecha de necesidad"])
    iso = df_dem["Fecha_DT"].dt.isocalendar()
    df_dem["Semana_Label"] = iso.year.astype(str) + "-W" + iso.week.astype(str).str.zfill(2)

    # Detectar columna cliente
    col_cli_dem = detectar_columna_cliente(df_dem)
    col_cli_cli = detectar_columna_cliente(df_cli)

    if not col_cli_dem or not col_cli_cli:
        st.error("❌ No se puede identificar la columna de cliente.")
        return

    # Unificar data
    df = df_dem.merge(df_mat, on=["Material", "Unidad"], how="left")
    df = df.merge(df_cli, left_on=col_cli_dem, right_on=col_cli_cli, how="left")

    # Costes
    DG, MCH = detectar_centros(leer_capacidades(df_cap))
    capacidades = leer_capacidades(df_cap)

    col_cost_dg = next((c for c in df.columns if "cost" in c.lower() and "dg" in c.lower()), None)
    col_cost_mch = next((c for c in df.columns if "cost" in c.lower() and "mch" in c.lower()), None)

    def elegir_centro(r):
        c1 = to_float_safe(r.get(col_cost_dg, 0))
        c2 = to_float_safe(r.get(col_cost_mch, 0))
        return DG if c1 < c2 else MCH

    df["Centro_Base"] = df.apply(elegir_centro, axis=1)

    # Agrupación base
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

    # ====================================================
    # EJECUTAR CÁLCULO
    # ====================================================
    st.markdown("#### 🚀 Ejecutar planificación")
    if st.button("⚙️ Ejecutar cálculo inicial", use_container_width=True):

        with st.spinner("Generando planificación..."):

            g["Centro"] = g["Centro"].apply(norm_code)
            df_base = modo_C(
                df_agr=g[["Material", "Unidad", "Centro", "Cantidad", "Fecha", "Semana"]],
                df_mat=df_mat,
                capacidades=capacidades,
                DG_code=DG,
                MCH_code=MCH
            )

            st.session_state.df_base = df_base
            st.session_state.capacidades_calc = capacidades
            st.session_state.DG_calc = DG
            st.session_state.MCH_calc = MCH

        st.success("✔ Cálculo inicial completado.")
        guardar_historial("Inicial", st.session_state.usuario, df_base, DG, MCH)
        st.info("Historial actualizado.")

    # ====================================================
    # MOSTRAR RESULTADOS
    # ====================================================
    if "df_base" in st.session_state:

        df_base = st.session_state.df_base
        DG = st.session_state.DG_calc
        MCH = st.session_state.MCH_calc

        st.markdown("---")
        st.markdown("### 📊 Resultados del cálculo inicial")

        c = st.columns(3)
        c[0].metric("Total propuestas", f"{len(df_base):,}")
        c[1].metric(f"Horas {DG}", f"{df_base[df_base['Centro']==DG]['Horas'].sum():,.1f}h")
        c[2].metric(f"Horas {MCH}", f"{df_base[df_base['Centro']==MCH]['Horas'].sum():,.1f}h")

        st.markdown("#### 📈 Gráfico semanal")

        df_plot = df_base.copy()
        df_plot["Semana"] = df_plot["Semana"].astype(str)
        df_plot["Centro"] = df_plot["Centro"].astype(str)

        carga = (
            df_plot.groupby(["Semana","Centro"])["Horas"]
            .sum().unstack().fillna(0)
        )

        st.bar_chart(carga)
        st.dataframe(carga.style.format("{:,.1f}"))

        st.markdown("#### 📝 Detalle de propuestas")
        st.dataframe(df_base)

        # DESCARGA
        path_ini = os.path.join(UPLOAD_DIR, f"Propuesta_Inicial_{datetime.now().strftime('%Y%m%d')}.xlsx")
        df_base.to_excel(path_ini, index=False)
        with open(path_ini, "rb") as f:
            st.download_button("📥 Descargar Excel inicial", data=f, file_name="Propuesta_Inicial.xlsx")

        # ====================================================
        # AJUSTE SEMANAL
        # ====================================================
        st.markdown("---")
        st.markdown("### 🎛️ Ajuste por semana (DG/MCH)")

        semanas = sorted(df_base["Semana"].astype(str).unique())
        ajustes = {}

        cols = st.columns(4)
        for i, sem in enumerate(semanas):
            with cols[i % 4]:
                ajustes[sem] = st.slider(f"Semana {sem}", 0, 100, 50)

        if st.button("🔁 Aplicar ajustes y replanificar", use_container_width=True):
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

            guardar_historial("Reajustado", st.session_state.usuario, df_final, DG, MCH)
            st.success("✔ Replanificación completa")
            st.info("Historial actualizado.")

    # ====================================================
    # RESULTADOS REPLANIFICADOS
    # ====================================================
    if "df_replan" in st.session_state:
        df_final = st.session_state.df_replan

        st.markdown("---")
        st.markdown("### 📈 Resultados tras replanificación")

        c = st.columns(3)
        c[0].metric("Total propuestas", f"{len(df_final):,}")
        c[1].metric(f"Horas {DG}", f"{df_final[df_final['Centro']==DG]['Horas'].sum():,.1f}h")
        c[2].metric(f"Horas {MCH}", f"{df_final[df_final['Centro']==MCH]['Horas'].sum():,.1f}h")

        dfp = df_final.copy()
        dfp["Semana"] = dfp["Semana"].astype(str)
        dfp["Centro"] = dfp["Centro"].astype(str)

        carga2 = (
            dfp.groupby(["Semana","Centro"])["Horas"]
            .sum().unstack().fillna(0)
        )

        st.bar_chart(carga2)
        st.dataframe(carga2.style.format("{:,.1f}"))

        st.markdown("#### 📝 Detalle final")
        st.dataframe(df_final)

        path_final = os.path.join(UPLOAD_DIR, f"Propuesta_Replanificada_{datetime.now().strftime('%Y%m%d')}.xlsx")
        df_final.to_excel(path_final, index=False)

        with open(path_final, "rb") as f:
            st.download_button("📥 Descargar Excel replanificado", data=f, file_name="Propuesta_Replanificada.xlsx")


# -------- INTEGRACIÓN EN ROUTER --------
if page == "Órdenes de fabricación":
    pagina_ordenes_fabricacion()
# ================================
# PROYECTO‑X — BLOQUE 4/4
# Router final + Footer
# ================================

# ========== ROUTER DEFINITIVO ==========
if page == "Tablas maestras":
    pagina_tablas_maestras()

elif page == "Set Up Planning":
    st.info("🛠️ Pantalla disponible para futuras funciones.")

elif page == "Lanzamientos":
    st.info("📦 Pantalla de lanzamientos (pendiente de implementación).")

elif page == "Órdenes de fabricación":
    pagina_ordenes_fabricacion()

elif page == "Consulta / Trazabilidad":
    st.info("🔍 Pantalla de consulta / trazabilidad (pendiente de diseño).")

elif page == "Historial":
    mostrar_historial()

elif page == "Administración":
    st.info("⚙️ Pantalla de administración (pendiente).")

# ========== FOOTER CORPORATIVO ==========
st.markdown("---")
st.markdown(
    """
    <div class="footer">
        <p>💧 <strong>Proyecto‑X</strong> — Sistema de planificación completo<br>
        Desarrollado para uso interno · GRIFOLS</p>
    </div>
    """,
    unsafe_allow_html=True
)
