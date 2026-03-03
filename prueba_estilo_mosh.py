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
div.stButton > button {
    background-color: #FF4B4B;
    color: white;
    border-radius: 5px;
    font-weight: bold;
    width: 100%;
}
[data-testid="stSidebar"] {
    background-color: #004d85;
}
.mosh-logo {
    color: white;
    font-size: 36px;
    font-weight: bold;
    text-align: center;
    margin-bottom: 20px;
}
.btn-azul > button {
    background-color: #4da6ff !important;
    color: white !important;
    border-radius: 6px !important;
    font-weight: bold !important;
    width: 100% !important;
}
.section-container {
    background-color: #f8f9fa;
    padding: 1rem;
    border-radius: 10px;
    border-left: 5px solid #1f77b4;
    margin-bottom: 1rem;
}
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
defaults = {
    "autenticado": False,
    "usuario": "",
    "current_page": "Tablas maestras",
    "df_cap": None,
    "df_mat": None,
    "df_cli": None,
    "df_dem": None
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

UPLOAD_DIR = "archivos_cargados"
os.makedirs(UPLOAD_DIR, exist_ok=True)
HIST_PATH = os.path.join(UPLOAD_DIR, "historial_ejecuciones.xlsx")

# ---------- LOGIN ----------
if not st.session_state.autenticado:
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
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
    st.markdown("<div style='color:#003366;font-size:24px;font-weight:bold;text-align:right;'>GRIFOLS</div>", unsafe_allow_html=True)

st.write("---")
st.write(f"## {st.session_state.current_page}")
st.write(f"Bienvenido, **{st.session_state.usuario}**.")

page = st.session_state.current_page

# ---------- UTILIDADES ----------
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
    return digits.zfill(4) if digits else s

def semana_iso_str_from_ts(ts):
    ts = pd.to_datetime(ts, errors="coerce")
    if pd.isna(ts):
        return ""
    iso = ts.isocalendar()
    try:
        year = int(iso.year)
        week = int(iso.week)
    except Exception:
        year = int(iso["year"])
        week = int(iso["week"])
    return f"{year}-W{week:02d}"

def detectar_columna_cliente(df):
    posibles = ["cliente","client","customer","id cliente","codigo cliente","cod cliente","cliente id","sap cliente"]
    cols = {c: c.lower().strip() for c in df.columns}
    for orig, low in cols.items():
        for p in posibles:
            if p == low or p in low:
                return orig
    return None

def guardar_archivo_subido(archivo, nombre):
    t = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta = os.path.join(UPLOAD_DIR, f"{nombre} {t}.xlsx")
    with open(ruta, "wb") as f:
        f.write(archivo.getbuffer())
    return ruta
# ================================
# PROYECTO‑X — BLOQUE 2/4
# Tablas maestras (Carga de excels)
# ================================

def limpiar_estado_planificacion():
    for k in ("df_base","df_replan","capacidades_calc","DG_calc","MCH_calc"):
        if k in st.session_state:
            del st.session_state[k]

def pagina_tablas_maestras():
    st.markdown("### 📥 Carga de archivos maestros")

    # -------- CAPACIDAD --------
    st.markdown('<div class="section-container">', unsafe_allow_html=True)
    st.markdown("#### 🏭 Capacidad de planta")
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
            st.error(f"❌ Error al leer capacidad: {e}")
    else:
        st.info("Sube el archivo de capacidad.")
    st.markdown('</div>', unsafe_allow_html=True)

    # -------- MATERIALES --------
    st.markdown('<div class="section-container">', unsafe_allow_html=True)
    st.markdown("#### 📦 Maestro de materiales")
    f2 = st.file_uploader("Subir archivo de Materiales (.xlsx)", type=["xlsx"], key="mat")

    if f2:
        try:
            df_mat = pd.read_excel(f2)
            st.session_state.df_mat = df_mat.copy()
            limpiar_estado_planificacion()
            guardar_archivo_subido(f2, "Materiales")
            st.success("✔ Materiales cargado correctamente.")
            st.dataframe(df_mat, use_container_width=True, height=350)
        except Exception as e:
            st.error(f"❌ Error materiales: {e}")
    else:
        st.info("Sube el archivo de materiales.")
    st.markdown('</div>', unsafe_allow_html=True)

    # -------- CLIENTES --------
    st.markdown('<div class="section-container">', unsafe_allow_html=True)
    st.markdown("#### 👥 Maestro de clientes")
    f3 = st.file_uploader("Subir archivo de Clientes (.xlsx)", type=["xlsx"], key="cli")

    if f3:
        try:
            df_cli = pd.read_excel(f3)
            st.session_state.df_cli = df_cli.copy()
            limpiar_estado_planificacion()
            guardar_archivo_subido(f3, "Clientes")
            st.success("✔ Clientes cargado correctamente.")
            st.dataframe(df_cli, use_container_width=True, height=350)
        except Exception as e:
            st.error(f"❌ Error clientes: {e}")
    else:
        st.info("Sube el archivo de clientes.")
    st.markdown('</div>', unsafe_allow_html=True)

    # -------- DEMANDA --------
    st.markdown('<div class="section-container">', unsafe_allow_html=True)
    st.markdown("#### 📈 Demanda")
    f4 = st.file_uploader("Subir archivo de Demanda (.xlsx)", type=["xlsx"], key="dem")

    if f4:
        try:
            df_dem = pd.read_excel(f4)
            st.session_state.df_dem = df_dem.copy()
            limpiar_estado_planificacion()
            guardar_archivo_subido(f4, "Demanda")
            st.success("✔ Demanda cargada correctamente.")
            st.dataframe(df_dem, use_container_width=True, height=350)
        except Exception as e:
            st.error(f"❌ Error demanda: {e}")
    else:
        st.info("Sube el archivo de demanda.")
    st.markdown('</div>', unsafe_allow_html=True)

    # -------- VALIDACIÓN GLOBAL --------
    if all([
        st.session_state.df_cap is not None,
        st.session_state.df_mat is not None,
        st.session_state.df_cli is not None,
        st.session_state.df_dem is not None
    ]):
        st.success("🎉 ¡Todos los archivos han sido cargados!")
        st.info("Ir a 👉 **🏭 Órdenes de fabricación** para planificar.")
    else:
        st.warning("⚠️ Faltan archivos por cargar.")
        # ================================
# PROYECTO‑X — BLOQUE 3/4
# PLANIFICADOR COMPLETO + REPLANIFICACIÓN + HISTORIAL
# ================================

# -------- HISTORIAL --------
def guardar_historial(tipo, usuario, df_resultado, dg, mch):
    if df_resultado is None or len(df_resultado) == 0:
        return
    registro = pd.DataFrame([{
        "Fecha ejecución": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Usuario": usuario,
        "Tipo de ejecución": tipo,
        "Total propuestas": len(df_resultado),
        "Horas DG": df_resultado[df_resultado["Centro"] == dg]["Horas"].sum(),
        "Horas MCH": df_resultado[df_resultado["Centro"] == mch]["Horas"].sum()
    }])
    if os.path.exists(HIST_PATH):
        hist = pd.read_excel(HIST_PATH)
        hist = pd.concat([hist, registro], ignore_index=True)
    else:
        hist = registro
    hist.to_excel(HIST_PATH, index=False)

def mostrar_historial():
    st.markdown("### 📜 Historial de ejecuciones")
    if not os.path.exists(HIST_PATH):
        st.info("Aún no hay historial.")
        return
    df_hist = pd.read_excel(HIST_PATH)
    st.dataframe(df_hist, use_container_width=True, height=350)
    st.markdown('<div class="btn-azul">', unsafe_allow_html=True)
    with open(HIST_PATH, "rb") as f:
        st.download_button("📥 Descargar historial", f, file_name="historial_ejecuciones.xlsx")
    st.markdown('</div>', unsafe_allow_html=True)

# -------- CAPACIDADES --------
def leer_capacidades(df_cap):
    if df_cap is None:
        st.error("⚠️ No se cargó archivo de capacidad.")
        return {}
    if "Centro" not in df_cap.columns:
        st.error("⚠️ Falta columna 'Centro' en Capacidades.")
        return {}
    col_lower = {c: c.lower().strip() for c in df_cap.columns}
    cap_col = next((c for c,l in col_lower.items() if "capacidad" in l and "hora" in l), None)
    if not cap_col:
        st.error("⚠️ No se encontró la columna 'Capacidad horas'.")
        return {}
    capacidades = {}
    for _, r in df_cap.iterrows():
        capacidades[norm_code(r["Centro"])] = to_float_safe(r[cap_col], 0)
    return capacidades

def detectar_centros(capacidades):
    if not capacidades:
        return None, None
    keys = list(capacidades.keys())
    DG = next((k for k in keys if k.endswith("833")), keys[0])
    MCH = next((k for k in keys if k.endswith("184")), keys[-1])
    return DG, MCH

# -------- REPARTO --------
def repartir_porcentaje(df_semana, pct_dg, dg, mch):
    if pct_dg <= 0:
        df_semana["Centro"] = mch
        return df_semana
    if pct_dg >= 100:
        df_semana["Centro"] = dg
        return df_semana
    df_semana = df_semana.sort_values("Horas", ascending=False)
    total = df_semana["Horas"].sum()
    limite = total * (pct_dg / 100)
    acum, destinos = 0, []
    for _, r in df_semana.iterrows():
        if acum < limite:
            destinos.append(dg)
            acum += r["Horas"]
        else:
            destinos.append(mch)
    df_semana["Centro"] = destinos
    return df_semana

# -------- MODO C --------
def modo_C(df_agr, df_mat, capacidades, DG_code, MCH_code):
    tiempos = df_mat[[
        "Material","Unidad",
        "Tiempo fabricación unidad DG",
        "Tiempo fabricación unidad MCH",
        "Tamaño lote mínimo","Tamaño lote máximo"
    ]].drop_duplicates()

    df = df_agr.merge(tiempos, on=["Material","Unidad"], how="left")

    capacidad_restante = {}

    def cap_rest(c,f):
        key = (c,f)
        if key not in capacidad_restante:
            capacidad_restante[key] = capacidades.get(c, 0)
        return capacidad_restante[key]

    def consumir(c,f,h):
        capacidad_restante[(c,f)] = max(0, cap_rest(c,f) - h)

    def horas_necesarias(c, qty, fila):
        tu = to_float_safe(fila["Tiempo fabricación unidad DG"]) if c == DG_code \
             else to_float_safe(fila["Tiempo fabricación unidad MCH"])
        return qty * tu

    out, pid = [], 1

    for _, fila in df.iterrows():
        centro = norm_code(fila["Centro"])
        fecha = pd.to_datetime(fila["Fecha"]).normalize()
        semana = semana_iso_str_from_ts(fecha)

        cantidad = to_float_safe(fila["Cantidad"])
        lote_min = to_float_safe(fila["Tamaño lote mínimo"])
        lote_max = max(to_float_safe(fila["Tamaño lote máximo"], 1), 1)
        total = max(cantidad, lote_min)

        partes = []
        pendiente = total
        while pendiente > 0:
            q = min(pendiente, lote_max)
            partes.append(round(q,2))
            pendiente -= q

        for ql in partes:
            p = ql
            while p > 0:
                cap = cap_rest(centro, fecha)
                hnec = horas_necesarias(centro, p, fila)

                if cap >= hnec:
                    consumir(centro, fecha, hnec)
                    out.append({
                        "Nº de propuesta": pid,
                        "Material": fila["Material"],
                        "Centro": centro,
                        "Clase de orden": "NORM",
                        "Cantidad a fabricar": round(p,2),
                        "Unidad": fila["Unidad"],
                        "Fecha": fecha.strftime("%d.%m.%Y"),
                        "Semana": semana
                    })
                    pid += 1
                    p = 0
                else:
                    if cap > 0:
                        tu = (to_float_safe(fila["Tiempo fabricación unidad DG"])
                              if centro == DG_code
                              else to_float_safe(fila["Tiempo fabricación unidad MCH"]))
                        posible = cap / tu
                        posible = max(posible, 0)

                        consumir(centro, fecha, cap)
                        out.append({
                            "Nº de propuesta": pid,
                            "Material": fila["Material"],
                            "Centro": centro,
                            "Clase de orden": "NORM",
                            "Cantidad a fabricar": round(posible,2),
                            "Unidad": fila["Unidad"],
                            "Fecha": fecha.strftime("%d.%m.%Y"),
                            "Semana": semana
                        })
                        pid += 1
                        p -= posible

                    fecha += timedelta(days=1)
                    semana = semana_iso_str_from_ts(fecha)

    df_out = pd.DataFrame(out)

    tiempos2 = df_mat[[
        "Material","Unidad",
        "Tiempo fabricación unidad DG",
        "Tiempo fabricación unidad MCH"
    ]].drop_duplicates()

    df_out = df_out.merge(tiempos2, on=["Material","Unidad"], how="left")
    df_out["Horas"] = np.where(
        df_out["Centro"] == DG_code,
        df_out["Cantidad a fabricar"] * df_out["Tiempo fabricación unidad DG"],
        df_out["Cantidad a fabricar"] * df_out["Tiempo fabricación unidad MCH"]
    )
    return df_out

# -------- REPLANIFICACIÓN --------
def replanificar(df_base, df_mat, capacidades, DG_code, MCH_code, ajustes):
    df_finales = []
    for sem in sorted(df_base["Semana"].astype(str).unique()):
        df_sem = df_base[df_base["Semana"].astype(str)==sem].copy()
        pct = ajustes.get(sem, 50)
        df_sem = repartir_porcentaje(df_sem, pct, DG_code, MCH_code)
        df_finales.append(df_sem)

    df_adj = pd.concat(df_finales, ignore_index=True)
    df_adj_pre = df_adj.rename(columns={"Cantidad a fabricar":"Cantidad"})[
        ["Material","Unidad","Centro","Cantidad","Fecha","Semana"]
    ]
    return modo_C(df_adj_pre, df_mat, capacidades, DG_code, MCH_code)

# -------- PÁGINA: ÓRDENES DE FABRICACIÓN --------
def pagina_ordenes_fabricacion():
    st.markdown("### 🏭 Planificación de Órdenes de Fabricación")

    # Validar cargas
    if not all([
        st.session_state.df_cap,
        st.session_state.df_mat,
        st.session_state.df_cli,
        st.session_state.df_dem
    ]):
        st.warning("⚠️ Debes cargar todos los maestros en Tablas maestras.")
        return

    df_cap = st.session_state.df_cap
    df_mat = st.session_state.df_mat
    df_cli = st.session_state.df_cli
    df_dem = st.session_state.df_dem

    df_dem = df_dem.copy()
    df_dem["Fecha_DT"] = pd.to_datetime(df_dem["Fecha de necesidad"])
    iso = df_dem["Fecha_DT"].dt.isocalendar()
    df_dem["Semana_Label"] = iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)

    col_cli_dem = detectar_columna_cliente(df_dem)
    col_cli_cli = detectar_columna_cliente(df_cli)
    if not col_cli_dem or not col_cli_cli:
        st.error("No se pudo identificar la columna de cliente.")
        return

    df = df_dem.merge(df_mat, on=["Material","Unidad"], how="left")
    df = df.merge(df_cli, left_on=col_cli_dem, right_on=col_cli_cli, how="left")

    capacidades = leer_capacidades(df_cap)
    DG, MCH = detectar_centros(capacidades)

    col_cost_dg = next((c for c in df.columns if "cost" in c.lower() and "dg" in c.lower()), None)
    col_cost_mch = next((c for c in df.columns if "cost" in c.lower() and "mch" in c.lower()), None)

    def elegir_centro(r):
        c1 = to_float_safe(r.get(col_cost_dg, 0))
        c2 = to_float_safe(r.get(col_cost_mch, 0))
        return DG if c1 < c2 else MCH

    df["Centro_Base"] = df.apply(elegir_centro, axis=1)

    g = df.groupby(
        ["Material","Unidad","Centro_Base","Fecha de necesidad","Semana_Label"]
    ).agg({
        "Cantidad":"sum",
        "Tamaño lote mínimo":"first",
        "Tamaño lote máximo":"first"
    }).reset_index()

    g = g.rename(columns={
        "Centro_Base":"Centro",
        "Fecha de necesidad":"Fecha",
        "Semana_Label":"Semana"
    })

    st.markdown("#### 🚀 Ejecutar planificación")
    if st.button("⚙️ Ejecutar cálculo inicial", use_container_width=True):
        with st.spinner("Calculando..."):
            g["Centro"] = g["Centro"].apply(norm_code)
            df_base = modo_C(
                df_agr=g[["Material","Unidad","Centro","Cantidad","Fecha","Semana"]],
                df_mat=df_mat,
                capacidades=capacidades,
                DG_code=DG,
                MCH_code=MCH
            )
            st.session_state.df_base = df_base
            st.session_state.capacidades_calc = capacidades
            st.session_state.DG_calc = DG
            st.session_state.MCH_calc = MCH

        guardar_historial("Inicial", st.session_state.usuario, df_base, DG, MCH)
        st.success("✔ Cálculo inicial completado.")

    # RESULTADOS INICIALES
    if "df_base" in st.session_state and st.session_state.df_base is not None:

        df_base = st.session_state.df_base
        DG = st.session_state.DG_calc
        MCH = st.session_state.MCH_calc

        st.markdown("---")
        st.markdown("### 📊 Resultados iniciales")

        c = st.columns(3)
        c[0].metric("Total propuestas", f"{len(df_base):,}")
        c[1].metric(f"Horas {DG}", f"{df_base[df_base['Centro']==DG]['Horas'].sum():,.1f}h")
        c[2].metric(f"Horas {MCH}", f"{df_base[df_base['Centro']==MCH]['Horas'].sum():,.1f}h")

        dfp = df_base.copy()
        dfp["Semana"] = dfp["Semana"].astype(str)
        dfp["Centro"] = dfp["Centro"].astype(str)

        carga = dfp.groupby(["Semana","Centro"])["Horas"].sum().unstack().fillna(0)
        st.bar_chart(carga)
        st.dataframe(carga.style.format("{:,.1f}"))

        st.markdown("#### 📝 Detalle")
        st.dataframe(df_base)

        path_ini = os.path.join(UPLOAD_DIR, f"Propuesta_Inicial_{datetime.now().strftime('%Y%m%d')}.xlsx")
        df_base.to_excel(path_ini, index=False)
        with st.expander("📥 Descargar Excel"):
            with open(path_ini, "rb") as f:
                st.download_button("Descargar Propuesta Inicial", f, file_name="Propuesta_Inicial.xlsx")

        # REPLANIFICACIÓN
        st.markdown("---")
        st.markdown("### 🎛️ Ajuste por semana (0% MCH → 100% DG)")

        semanas = sorted(df_base["Semana"].astype(str).unique())
        ajustes = {}
        cols = st.columns(4)
        for i, sem in enumerate(semanas):
            with cols[i % 4]:
                ajustes[sem] = st.slider(f"Semana {sem}", 0, 100, 50)

        if st.button("🔁 Replanificar", use_container_width=True):
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
            st.success("✔ Replanificación completada.")

    # RESULTADOS FINALES
    if "df_replan" in st.session_state and st.session_state.df_replan is not None:

        df_final = st.session_state.df_replan
        DG = st.session_state.DG_calc
        MCH = st.session_state.MCH_calc

        st.markdown("---")
        st.markdown("### 📈 Resultados tras replanificación")

        c2 = st.columns(3)
        c2[0].metric("Total propuestas", f"{len(df_final):,}")
        c2[1].metric(f"Horas {DG}", f"{df_final[df_final['Centro']==DG]['Horas'].sum():,.1f}h")
        c2[2].metric(f"Horas {MCH}", f"{df_final[df_final['Centro']==MCH]['Horas'].sum():,.1f}h")

        dfp2 = df_final.copy()
        dfp2["Semana"] = dfp2["Semana"].astype(str)
        dfp2["Centro"] = dfp2["Centro"].astype(str)
        carga2 = dfp2.groupby(["Semana","Centro"])["Horas"].sum().unstack().fillna(0)
        st.bar_chart(carga2)
        st.dataframe(carga2.style.format("{:,.1f}"))

        st.markdown("#### 📝 Detalle final")
        st.dataframe(df_final)

        path_fin = os.path.join(UPLOAD_DIR, f"Propuesta_Replanificada_{datetime.now().strftime('%Y%m%d')}.xlsx")
        df_final.to_excel(path_fin, index=False)
        with st.expander("📥 Descargar Excel"):
            with open(path_fin, "rb") as f:
                st.download_button("Descargar Propuesta Replanificada", f, file_name="Propuesta_Replanificada.xlsx")
# ================================
# PROYECTO‑X — BLOQUE 4/4
# Router final + Footer corporativo
# ================================

if page == "Tablas maestras":
    pagina_tablas_maestras()

elif page == "Set Up Planning":
    st.info("🛠️ Pantalla disponible para futuras funciones.")

elif page == "Lanzamientos":
    st.info("📦 Pantalla de lanzamientos (pendiente de implementación).")

elif page == "Órdenes de fabricación":
    pagina_ordenes_fabricacion()

elif page == "Consulta / Trazabilidad":
    st.info("🔍 Pantalla de consulta / trazabilidad (pendiente).")

elif page == "Historial":
    mostrar_historial()

elif page == "Administración":
    st.info("⚙️ Pantalla de administración (pendiente).")

# ---------- FOOTER ----------
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
