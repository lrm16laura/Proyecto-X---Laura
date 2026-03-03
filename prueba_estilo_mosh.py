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
    st.session_state.current_page = "Tablas maestras"   # flujo deseado

# DataFrames de trabajo
for key in ("df_cap", "df_mat", "df_cli", "df_dem"):
    if key not in st.session_state:
        st.session_state[key] = None

# Rutas
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
        password_input = st.text_input("Contraseña:", type="password")  # simulado
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

    def set_page(name: str):
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
h1, h2 = st.columns([10,2])
with h1:
    st.write("≡")
with h2:
    st.markdown("<div style='font-size:24px;font-weight:bold;color:#003366;text-align:right;'>GRIFOLS</div>", unsafe_allow_html=True)

st.write("---")
st.write(f"## {st.session_state.current_page}")
st.write(f"Bienvenido, **{st.session_state.usuario}**.")

# Página actual
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
    # En pandas recientes iso es un objeto con .year/.week o un df con ["year"]["week"]
    year = getattr(iso, "year", getattr(iso, 0))
    week = getattr(iso, "week", getattr(iso, 0))
    # Si viniese como DataFrame-like, resolvemos por índice
    try:
        if hasattr(iso, "__getitem__"):
            year = iso["year"]
            week = iso["week"]
    except Exception:
        pass
    return f"{int(year)}-W{int(week):02d}"

def detectar_columna_cliente(df):
    posibles = [
        "cliente","client","customer",
        "id cliente","codigo cliente","cod cliente",
        "cliente id","sap cliente"
    ]
    low = {c: c.lower().strip() for c in df.columns}
    for orig, l in low.items():
        for p in posibles:
            if p == l or p in l:
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
    for k in ("df_base", "df_replan", "capacidades_calc", "DG_calc", "MCH_calc"):
        if k in st.session_state:
            del st.session_state[k]

def pagina_tablas_maestras():
    st.markdown("### 📥 Carga de archivos maestros")

    # 1) CAPACIDAD
    st.markdown('<div class="section-container">', unsafe_allow_html=True)
    st.markdown("#### 🏭 Capacidad de planta (horas por Centro)")

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

    # 2) MATERIALES
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

    # 3) CLIENTES
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

    # 4) DEMANDA
    st.markdown('<div class="section-container">', unsafe_allow_html=True)
    st.markdown("#### 📈 Demanda (Fecha de necesidad + Cantidad por Material)")

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

    # Validación global
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
        # ================================
# PROYECTO‑X — BLOQUE 3/4
# PLANIFICADOR + REPLANIFICACIÓN + HISTORIAL + PÁGINAS
# ================================

# -------- HISTORIAL --------
def guardar_historial(tipo, usuario, df_resultado, dg, mch):
    """Guarda un registro (Inicial/Reajustado) en 'historial_ejecuciones.xlsx'."""
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

    if os.path.exists(HIST_PATH):
        hist = pd.read_excel(HIST_PATH)
        hist = pd.concat([hist, registro], ignore_index=True)
    else:
        hist = registro

    hist.to_excel(HIST_PATH, index=False)
    return HIST_PATH

def mostrar_historial():
    st.markdown("### 📜 Historial de ejecuciones")
    if not os.path.exists(HIST_PATH):
        st.info("Todavía no existe ningún historial.")
        return
    df_hist = pd.read_excel(HIST_PATH)
    if df_hist.empty:
        st.info("No hay ejecuciones registradas aún.")
        return
    st.dataframe(df_hist, use_container_width=True, height=360)
    st.markdown('<div class="btn-azul">', unsafe_allow_html=True)
    with open(HIST_PATH, "rb") as f:
        st.download_button(
            "📥 Descargar historial",
            data=f,
            file_name="historial_ejecuciones.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    st.markdown('</div>', unsafe_allow_html=True)

# -------- PLANIFICADOR: CAPACIDADES --------
def leer_capacidades(df_cap):
    """Devuelve {centro_normalizado: capacidad_horas}."""
    if df_cap is None:
        st.error("No se cargó el archivo de capacidad.")
        return {}

    if "Centro" not in df_cap.columns:
        st.error("❌ Falta la columna 'Centro' en Capacidad.")
        return {}

    # localizar columna de capacidad (flexible)
    col_lower = {c: c.lower().strip() for c in df_cap.columns}
    cap_col = None
    for c, low in col_lower.items():
        if "capacidad" in low and "hora" in low:
            cap_col = c
            break
    if cap_col is None:
        st.error("❌ No se encontró la columna de 'Capacidad horas'.")
        return {}

    capacidades = {}
    for _, row in df_cap.iterrows():
        capacidades[norm_code(row["Centro"])] = to_float_safe(row[cap_col], 0)
    return capacidades

def detectar_centros(capacidades: dict):
    """Heurística para detectar DG y MCH por sufijos típicos."""
    if not capacidades:
        return None, None
    keys = list(capacidades.keys())
    DG = next((k for k in keys if k.endswith("833")), keys[0])
    MCH = next((k for k in keys if k.endswith("184")), keys[-1])
    return DG, MCH

# -------- PLANIFICADOR: REPARTO PORCENTAJE --------
def repartir_porcentaje(df_semana, pct_dg, dg, mch):
    """Reparte líneas de una semana entre DG/MCH según % objetivo."""
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

# -------- PLANIFICADOR: MODO C --------
def modo_C(df_agr, df_mat, capacidades, DG_code, MCH_code):
    """
    Planificador con:
    - capacidad diaria
    - lotes mínimos/máximos
    - empuje al día siguiente si no cabe
    """
    tiempos = df_mat[[
        "Material","Unidad",
        "Tiempo fabricación unidad DG",
        "Tiempo fabricación unidad MCH",
        "Tamaño lote mínimo","Tamaño lote máximo"
    ]].drop_duplicates()

    df = df_agr.merge(tiempos, on=["Material","Unidad"], how="left")

    capacidad_restante = {}  # (centro, fecha) -> horas disponibles

    def cap_rest(centro, fecha):
        key = (centro, fecha)
        if key not in capacidad_restante:
            capacidad_restante[key] = capacidades.get(centro, 0)
        return capacidad_restante[key]

    def consumir(centro, fecha, horas):
        capacidad_restante[(centro, fecha)] = max(0.0, cap_rest(centro, fecha) - horas)

    def horas_necesarias(centro, qty, fila):
        tu = to_float_safe(fila["Tiempo fabricación unidad DG"]) if centro == DG_code \
             else to_float_safe(fila["Tiempo fabricación unidad MCH"])
        return qty * tu

    out = []
    pid = 1

    for _, r in df.iterrows():
        centro = norm_code(r["Centro"])
        fecha = pd.to_datetime(r["Fecha"]).normalize()
        semana = semana_iso_str_from_ts(fecha)

        cantidad = to_float_safe(r.get("Cantidad", 0), 0)
        lote_min = to_float_safe(r.get("Tamaño lote mínimo", 0), 0)
        lote_max = to_float_safe(r.get("Tamaño lote máximo", 1), 1)

        total = max(cantidad, lote_min)
        lote_max = max(1.0, lote_max)

        # dividir en partes por lote_max
        partes, pendiente = [], total
        while pendiente > 0:
            q = min(pendiente, lote_max)
            partes.append(round(q, 2))
            pendiente -= q

        for ql in partes:
            p = ql
            while p > 0:
                cap = cap_rest(centro, fecha)
                hnec = horas_necesarias(centro, p, r)

                if cap >= hnec:
                    consumir(centro, fecha, hnec)
                    out.append({
                        "Nº de propuesta": pid,
                        "Material": r["Material"],
                        "Centro": centro,
                        "Clase de orden": "NORM",
                        "Cantidad a fabricar": round(p, 2),
                        "Unidad": r["Unidad"],
                        "Fecha": fecha.strftime("%d.%m.%Y"),
                        "Semana": semana
                    })
                    pid += 1
                    p = 0
                else:
                    if cap > 0:
                        tu = (to_float_safe(r["Tiempo fabricación unidad DG"])
                              if centro == DG_code
                              else to_float_safe(r["Tiempo fabricación unidad MCH"]))
                        posible = cap / tu
                        posible = max(posible, 0)

                        consumir(centro, fecha, cap)
                        out.append({
                            "Nº de propuesta": pid,
                            "Material": r["Material"],
                            "Centro": centro,
                            "Clase de orden": "NORM",
                            "Cantidad a fabricar": round(posible, 2),
                            "Unidad": r["Unidad"],
                            "Fecha": fecha.strftime("%d.%m.%Y"),
                            "Semana": semana
                        })
                        pid += 1
                        p -= posible

                    # siguiente día
                    fecha += timedelta(days=1)
                    semana = semana_iso_str_from_ts(fecha)

    df_out = pd.DataFrame(out)

    # Recalcular horas
    tiempos2 = df_mat[["Material","Unidad",
                       "Tiempo fabricación unidad DG",
                       "Tiempo fabricación unidad MCH"]].drop_duplicates()

    df_out = df_out.merge(tiempos2, on=["Material","Unidad"], how="left")
    df_out["Horas"] = np.where(
        df_out["Centro"] == DG_code,
        df_out["Cantidad a fabricar"] * df_out["Tiempo fabricación unidad DG"],
        df_out["Cantidad a fabricar"] * df_out["Tiempo fabricación unidad MCH"]
    )
    return df_out

# -------- PLANIFICADOR: REPLANIFICACIÓN --------
def replanificar(df_base, df_mat, capacidades, DG_code, MCH_code, ajustes):
    df_reps = []
    for sem in sorted(df_base["Semana"].astype(str).unique()):
        df_sem = df_base[df_base["Semana"].astype(str) == sem].copy()
        if df_sem.empty:
            continue
        pct = ajustes.get(sem, 50)
        df_sem = repartir_porcentaje(df_sem, pct, DG_code, MCH_code)
        df_reps.append(df_sem)

    if not df_reps:
        return df_base.copy()

    df_adj = pd.concat(df_reps, ignore_index=True)
    df_adj_pre = df_adj.rename(columns={"Cantidad a fabricar": "Cantidad"})[
        ["Material","Unidad","Centro","Cantidad","Fecha","Semana"]
    ]
    return modo_C(df_adj_pre, df_mat, capacidades, DG_code, MCH_code)

# -------- PÁGINA: ÓRDENES DE FABRICACIÓN --------
def pagina_ordenes_fabricacion():
    st.markdown("### 🏭 Planificación de Órdenes de Fabricación")

    # Validar cargas
    if not all([
        st.session_state.df_cap is not None,
        st.session_state.df_mat is not None,
        st.session_state.df_cli is not None,
        st.session_state.df_dem is not None
    ]):
        st.warning("⚠️ Primero debes cargar todos los maestros en **🗺️ Tablas maestras**.")
        return

    df_cap = st.session_state.df_cap
    df_mat = st.session_state.df_mat
    df_cli = st.session_state.df_cli
    df_dem = st.session_state.df_dem

    # Demanda + semana ISO
    df_dem = df_dem.copy()
    df_dem["Fecha_DT"] = pd.to_datetime(df_dem["Fecha de necesidad"])
    iso = df_dem["Fecha_DT"].dt.isocalendar()
    # usar índices para compatibilidad de pandas
    df_dem["Semana_Label"] = iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)

    col_cli_dem = detectar_columna_cliente(df_dem)
    col_cli_cli = detectar_columna_cliente(df_cli)
    if not col_cli_dem or not col_cli_cli:
        st.error("❌ No se pudo identificar la columna de cliente en Demanda/Clientes.")
        return

    df = df_dem.merge(df_mat, on=["Material","Unidad"], how="left")
    df = df.merge(df_cli, left_on=col_cli_dem, right_on=col_cli_cli, how="left")

    # Capacidades y centros
    capacidades = leer_capacidades(df_cap)
    DG, MCH = detectar_centros(capacidades)

    # Selección de centro por coste (si existen columnas de coste)
    col_cost_dg = next((c for c in df.columns if "cost" in c.lower() and "dg" in c.lower()), None)
    col_cost_mch = next((c for c in df.columns if "cost" in c.lower() and "mch" in c.lower()), None)

    def elegir_centro(r):
        c1 = to_float_safe(r.get(col_cost_dg, 0))
        c2 = to_float_safe(r.get(col_cost_mch, 0))
        return DG if c1 < c2 else MCH

    df["Centro_Base"] = df.apply(elegir_centro, axis=1)

    # Agrupar para el modo C
    g = df.groupby(
        ["Material","Unidad","Centro_Base","Fecha de necesidad","Semana_Label"],
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

    st.markdown("#### 🚀 Ejecutar planificación")
    if st.button("⚙️ Ejecutar cálculo inicial", use_container_width=True):
        with st.spinner("Generando planificación..."):
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

        st.success("✔ Cálculo inicial completado.")
        guardar_historial("Inicial", st.session_state.usuario, df_base, DG, MCH)
        st.info("📜 Historial actualizado.")

    # Resultados iniciales
    if "df_base" in st.session_state and st.session_state.df_base is not None:
        df_base = st.session_state.df_base
        DG = st.session_state.DG_calc
        MCH = st.session_state.MCH_calc

        st.markdown("---")
        st.markdown("### 📊 Resultados del cálculo inicial")

        m = st.columns(3)
        m[0].metric("Total propuestas", f"{len(df_base):,}")
        m[1].metric(f"Horas {DG}", f"{df_base[df_base['Centro']==DG]['Horas'].sum():,.1f}h")
        m[2].metric(f"Horas {MCH}", f"{df_base[df_base['Centro']==MCH]['Horas'].sum():,.1f}h")

        st.markdown("#### 📈 Gráfico semanal")
        dfp = df_base.copy()
        dfp["Semana"] = dfp["Semana"].astype(str)
        dfp["Centro"] = dfp["Centro"].astype(str)
        carga = dfp.groupby(["Semana","Centro"])["Horas"].sum().unstack().fillna(0).sort_index()
        st.bar_chart(carga, use_container_width=True)
        st.dataframe(carga.style.format("{:,.1f}"), use_container_width=True)

        st.markdown("#### 📝 Detalle de propuestas")
        st.dataframe(df_base, use_container_width=True)

        path_ini = os.path.join(UPLOAD_DIR, f"Propuesta_Inicial_{datetime.now().strftime('%Y%m%d')}.xlsx")
        df_base.to_excel(path_ini, index=False)
        with st.expander("📥 Descargar Excel"):
            with open(path_ini, "rb") as f:
                st.download_button("Descargar Propuesta Inicial", data=f, file_name="Propuesta_Inicial.xlsx")

        # Ajuste semanal
        st.markdown("---")
        st.markdown("### 🎛️ Ajuste por semana (0% MCH · 100% DG)")
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
            st.success("✔ Replanificación completada.")
            st.info("📜 Historial actualizado.")

    # Resultados replanificados
    if "df_replan" in st.session_state and st.session_state.df_replan is not None:
        df_final = st.session_state.df_replan
        st.markdown("---")
        st.markdown("### 📈 Resultados tras replanificación")

        DG = st.session_state.DG_calc
        MCH = st.session_state.MCH_calc

        m2 = st.columns(3)
        m2[0].metric("Total propuestas", f"{len(df_final):,}")
        m2[1].metric(f"Horas {DG}", f"{df_final[df_final['Centro']==DG]['Horas'].sum():,.1f}h")
        m2[2].metric(f"Horas {MCH}", f"{df_final[df_final['Centro']==MCH]['Horas'].sum():,.1f}h")

        dfp2 = df_final.copy()
        dfp2["Semana"] = dfp2["Semana"].astype(str)
        dfp2["Centro"] = dfp2["Centro"].astype(str)
        carga2 = dfp2.groupby(["Semana","Centro"])["Horas"].sum().unstack().fillna(0).sort_index()
        st.bar_chart(carga2, use_container_width=True)
        st.dataframe(carga2.style.format("{:,.1f}"), use_container_width=True)

        st.markdown("#### 📝 Detalle final")
        st.dataframe(df_final, use_container_width=True)

        path_fin = os.path.join(UPLOAD_DIR, f"Propuesta_Replanificada_{datetime.now().strftime('%Y%m%d')}.xlsx")
        df_final.to_excel(path_fin, index=False)
        with st.expander("📥 Descargar Excel"):
            with open(path_fin, "rb") as f:
                st.download_button("Descargar Propuesta Replanificada", data=f, file_name="Propuesta_Replanificada.xlsx")
                # ================================
# PROYECTO‑X — BLOQUE 4/4
# Router final + Footer
# ================================

# ---------- ROUTER DEFINITIVO ----------
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

# ---------- FOOTER CORPORATIVO ----------
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
