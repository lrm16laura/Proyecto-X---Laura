# ============================================================
# SISTEMA DE CÁLCULO DE FABRICACIÓN — Planificación con ajuste semanal
# Versión 3 (UI limpia, título centrado, footer centrado, semanas ISO con "W")
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
import altair as alt

# ------------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA
# ------------------------------------------------------------
st.set_page_config(
    page_title="Sistema de Cálculo de Fabricación",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------------------------------------------------
# ESTILOS CSS (activado — título y footer centrados)
# ------------------------------------------------------------
st.markdown("""
<style>
.main { padding-top: 2rem; }

/* Título centrado */
h1 { 
    color: #1f77b4; 
    text-align: center;
    font-size: 2.5rem; 
    margin-bottom: 1rem; 
    display:flex; 
    align-items:center; 
    justify-content:center;
    gap:.6rem;
}

/* Subtítulo (bajo el título) */
.subtitle {
    text-align: center;
    font-size: 1.05rem;
    color: #2c3e50;
    margin-bottom: .5rem;
}

h2 { color: #2c3e50; border-bottom: 3px solid #1f77b4; padding-bottom: 0.5rem; }
.section-container {
    background-color: #f8f9fa;
    padding: 1.5rem;
    border-radius: 10px;
    border-left: 5px solid #1f77b4;
    margin-bottom: 1.5rem;
}

/* Footer centrado */
.footer {
    text-align: center;
    color: #7f8c8d;
    font-size: 0.95rem;
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 1px solid #ecf0f1;
}

.stButton > button { width: 100%; font-weight: bold; border-radius: 8px; }
.small-note { color:#7f8c8d; font-size:0.85rem; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# RUTA
# ------------------------------------------------------------
UPLOAD_DIR = "archivos_cargados"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ------------------------------------------------------------
# UTILIDADES
# ------------------------------------------------------------
def guardar_archivo(archivo, nombre):
    if archivo is not None:
        t = datetime.now().strftime("%Y%m%d_%H%M%S")
        p = os.path.join(UPLOAD_DIR, f"{nombre}_{t}.xlsx")
        with open(p, "wb") as f:
            f.write(archivo.getbuffer())
        return p

def to_float_safe(v, default=0.0):
    if pd.isna(v): return float(default)
    if isinstance(v, str):
        v = v.replace(",", ".").strip()
        if v == "": return float(default)
    try:
        return float(v)
    except:
        return float(default)

def norm_code(code):
    s = str(code).strip()
    if s.endswith(".0"): s = s[:-2]
    digits = "".join(ch for ch in s if ch.isdigit())
    if digits == "": return s
    if len(digits) < 4:
        digits = digits.zfill(4)
    return digits

def semana_iso_str_from_ts(ts: pd.Timestamp) -> str:
    """Devuelve semana ISO como 'YYYY-Www'."""
    iso = ts.isocalendar()
    return f"{int(iso.year)}-W{int(iso.week):02d}"

def semana_iso_str_from_date(dtobj) -> str:
    """Para objetos datetime.date/datetime, devuelve 'YYYY-Www'."""
    ts = pd.to_datetime(dtobj)
    return semana_iso_str_from_ts(ts)

# ------------------------------------------------------------
# DETECTAR COLUMNA CLIENTE
# ------------------------------------------------------------
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

# ------------------------------------------------------------
# LECTURA DE CAPACIDADES
# ------------------------------------------------------------
def leer_capacidades(df_cap):
    if "Centro" not in df_cap.columns:
        st.error("❌ Falta la columna 'Centro' en Capacidad")
        st.stop()

    col_lower = {c: c.lower().strip() for c in df_cap.columns}
    cap_col = None
    for c, low in col_lower.items():
        if low == "capacidad horas" or ("capacidad" in low and "hora" in low):
            cap_col = c
            break
    if cap_col is None:
        st.error("❌ No se encuentra la columna 'Capacidad horas' en Capacidad")
        st.stop()

    capacidades = {}
    for _, r in df_cap.iterrows():
        capacidades[norm_code(r["Centro"])] = to_float_safe(r[cap_col], 0)

    return capacidades

# ------------------------------------------------------------
# DETECTAR DG Y MCH
# ------------------------------------------------------------
def detectar_centros_desde_capacidades(capacidades):
    keys = list(capacidades.keys())
    DG = next((k for k in keys if k.endswith("833")), keys[0])
    MCH = next((k for k in keys if k.endswith("184")), keys[-1])
    return DG, MCH, keys

# ------------------------------------------------------------
# REPARTO POR SEMANA
# ------------------------------------------------------------
def repartir_porcentaje(df_semana, pct_dg, dg, mch):
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

# ------------------------------------------------------------
# Planificador por lotes con capacidad diaria
# ------------------------------------------------------------
def modo_C(df_agr, df_mat, capacidades, DG_code, MCH_code):
    tiempos = df_mat[[
        "Material","Unidad",
        "Tiempo fabricación unidad DG",
        "Tiempo fabricación unidad MCH",
        "Tamaño lote mínimo","Tamaño lote máximo"
    ]].drop_duplicates()

    df = df_agr.merge(tiempos, on=["Material","Unidad"], how="left")

    capacidad_restante = {}

    def get_cap(centro, fecha):
        key = (centro, fecha)
        if key not in capacidad_restante:
            capacidad_restante[key] = capacidades.get(centro, 0)
        return capacidad_restante[key]

    def consume(centro, fecha, h):
        nuevo = get_cap(centro, fecha) - h
        if nuevo < 0 and abs(nuevo) < 1e-9:
            nuevo = 0.0
        capacidad_restante[(centro, fecha)] = nuevo

    def horas_nec(centro, qty, r):
        tu = r["Tiempo fabricación unidad DG"] if centro == DG_code else r["Tiempo fabricación unidad MCH"]
        return qty * to_float_safe(tu)

    def cant_por_cap(centro, cap_h, r):
        tu = r["Tiempo fabricación unidad DG"] if centro == DG_code else r["Tiempo fabricación unidad MCH"]
        tu = to_float_safe(tu)
        if tu == 0: return 0
        return cap_h / tu

    out = []
    contador = 1

    for _, r in df.iterrows():
        centro = norm_code(r["Centro"])
        fecha = pd.to_datetime(r["Fecha"]).normalize()

        # Semana ISO de la fecha inicial
        semana = semana_iso_str_from_ts(fecha)

        cantidad = to_float_safe(r.get("Cantidad", 0), 0)
        lote_min = to_float_safe(r.get("Lote_min", r.get("Tamaño lote mínimo", 0)), 0)
        lote_max = to_float_safe(r.get("Lote_max", r.get("Tamaño lote máximo", 1)), 1)

        total = max(cantidad, lote_min)
        lote_max = max(1.0, lote_max)

        partes = []
        pendiente = total
        while pendiente > 0:
            q = min(pendiente, lote_max)
            partes.append(round(q,2))
            pendiente -= q

        for ql in partes:
            p = ql
            while p > 0:
                cap = get_cap(centro, fecha)
                hnec = horas_nec(centro, p, r)

                if cap >= hnec:
                    consume(centro, fecha, hnec)
                    out.append({
                        "Nº de propuesta": contador,
                        "Material": r["Material"],
                        "Centro": centro,
                        "Clase de orden": "NORM",
                        "Cantidad a fabricar": round(p,2),
                        "Unidad": r["Unidad"],
                        "Fecha": fecha.strftime("%d.%m.%Y"),
                        "Semana": semana,              # mantiene ISO con 'W'
                        "Lote_min": lote_min,
                        "Lote_max": lote_max
                    })
                    contador += 1
                    p = 0

                else:
                    posible = cant_por_cap(centro, cap, r)
                    if posible <= 0:
                        fecha += timedelta(days=1)
                        # Recalcular semana ISO cuando cambia el día
                        semana = semana_iso_str_from_ts(fecha)
                        continue

                    hprod = horas_nec(centro, posible, r)
                    consume(centro, fecha, hprod)

                    out.append({
                        "Nº de propuesta": contador,
                        "Material": r["Material"],
                        "Centro": centro,
                        "Clase de orden": "NORM",
                        "Cantidad a fabricar": round(posible,2),
                        "Unidad": r["Unidad"],
                        "Fecha": fecha.strftime("%d.%m.%Y"),
                        "Semana": semana,              # mantiene ISO con 'W'
                        "Lote_min": lote_min,
                        "Lote_max": lote_max
                    })
                    contador += 1
                    p -= posible

    return pd.DataFrame(out)

# ------------------------------------------------------------
# EJECUCIÓN COMPLETA (no usada directamente en UI, pero actualizada)
# ------------------------------------------------------------
def ejecutar_calculo(df_cap, df_mat, df_cli, df_dem, ajustes):
    capacidades = leer_capacidades(df_cap)
    DG, MCH, _ = detectar_centros_desde_capacidades(capacidades)

    df_dem = df_dem.copy()
    df_dem["Fecha_DT"] = pd.to_datetime(df_dem["Fecha de necesidad"])
    # Semana ISO con 'W'
    iso = df_dem["Fecha_DT"].dt.isocalendar()
    df_dem["Semana_Label"] = iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)

    col_cli_dem = detectar_columna_cliente(df_dem)
    col_cli_cli = detectar_columna_cliente(df_cli)
    if not col_cli_dem or not col_cli_cli:
        st.error("❌ No se encontró columna de cliente en Demanda o Clientes.")
        st.stop()

    df = df_dem.merge(df_mat, on=["Material","Unidad"], how="left")
    df = df.merge(df_cli, left_on=col_cli_dem, right_on=col_cli_cli, how="left")

    # Decisión por coste
    COL_COST_DG = next((c for c in df.columns if "dg" in c.lower() and "cost" in c.lower()), None)
    COL_COST_MCH = next((c for c in df.columns if "mch" in c.lower() and "cost" in c.lower()), None)

    def decidir(r):
        c1 = to_float_safe(r.get(COL_COST_DG,0))
        c2 = to_float_safe(r.get(COL_COST_MCH,0))
        return DG if c1 < c2 else MCH

    df["Centro_Base"] = df.apply(decidir, axis=1)

    g = df.groupby(
        ["Material","Unidad","Centro_Base","Fecha de necesidad","Semana_Label"], dropna=False
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

    g["Centro"] = g["Centro"].apply(norm_code)
    g["Lote_min"] = g["Tamaño lote mínimo"]
    g["Lote_max"] = g["Tamaño lote máximo"]

    df_c = modo_C(
        g[["Material","Unidad","Centro","Cantidad","Fecha","Semana","Lote_min","Lote_max"]],
        df_mat,
        capacidades,
        DG, MCH
    )

    tiempos = df_mat[[
        "Material","Unidad",
        "Tiempo fabricación unidad DG",
        "Tiempo fabricación unidad MCH"
    ]]

    df_c = df_c.merge(tiempos, on=["Material","Unidad"], how="left")

    df_c["Horas"] = np.where(
        df_c["Centro"] == DG,
        df_c["Cantidad a fabricar"] * df_c["Tiempo fabricación unidad DG"],
        df_c["Cantidad a fabricar"] * df_c["Tiempo fabricación unidad MCH"]
    )

    # ---- Ajuste por semana ----
    df_rep = []
    for sem in sorted(df_c["Semana"].dropna().astype(str).unique()):
        df_sem = df_c[df_c["Semana"].astype(str) == sem].copy()
        pct = ajustes.get(sem, 50)
        df_sem = repartir_porcentaje(df_sem, pct, DG, MCH)
        df_rep.append(df_sem)

    df_adj = pd.concat(df_rep, ignore_index=True)

    df_adj_pre = df_adj.rename(columns={"Cantidad a fabricar":"Cantidad"})[
        ["Material","Unidad","Centro","Cantidad","Fecha","Semana","Lote_min","Lote_max"]
    ]

    df_final = modo_C(df_adj_pre, df_mat, capacidades, DG, MCH)

    df_final = df_final.merge(tiempos, on=["Material","Unidad"], how="left")

    df_final["Horas"] = np.where(
        df_final["Centro"] == DG,
        df_final["Cantidad a fabricar"] * df_final["Tiempo fabricación unidad DG"],
        df_final["Cantidad a fabricar"] * df_final["Tiempo fabricación unidad MCH"]
    )

    return df_final, capacidades, DG, MCH

# ============================================================
# INTERFAZ — Encabezado + Tabs
# ============================================================
st.markdown('<h1>📊 Sistema de Cálculo de Fabricación</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="subtitle">'
    'Carga los 4 archivos Excel necesarios, se ejecutará una primera planificación, '
    'y en caso de ser necesario, ajusta los porcentajes por semana y genera la planificación completa.'
    '</p>',
    unsafe_allow_html=True
)
st.markdown("---")

tab1, tab2 = st.tabs(["📥 Carga de Archivos", "⚙️ Ajuste y Ejecución"])

# Variables de estado
df_cap = df_mat = df_cli = df_dem = None

# =========================
# TAB 1 — CARGA
# =========================
with tab1:
    st.subheader("📁 Carga tus archivos Excel")

    col1, col2 = st.columns(2)

    # Capacidad
    with col1:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 🏭 Capacidad de planta")
        f1 = st.file_uploader("Subir Capacidad (Capacidad horas por Centro)", type=["xlsx"], key="u1", label_visibility="collapsed")
        if f1:
            try:
                df_cap = pd.read_excel(f1)
                guardar_archivo(f1, "capacidad_planta")
                st.session_state.df_cap = df_cap.copy()
                st.success("✅ Cargado")
                st.dataframe(df_cap, use_container_width=True, height=150)
                st.caption("Lee exactamente la columna **Capacidad horas** por **Centro** (ej.: 0833=40, 0184=20).")
            except Exception as e:
                st.error(f"Error al leer Capacidad: {e}")
        else:
            st.info("Esperando archivo…")
        st.markdown('</div>', unsafe_allow_html=True)

    # Materiales
    with col2:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 📦 Maestro de materiales")
        f2 = st.file_uploader("Subir Materiales", type=["xlsx"], key="u2", label_visibility="collapsed")
        if f2:
            try:
                df_mat = pd.read_excel(f2)
                guardar_archivo(f2, "maestro_materiales")
                st.session_state.df_mat = df_mat.copy()
                st.success("✅ Cargado")
                st.dataframe(df_mat, use_container_width=True, height=400)
            except Exception as e:
                st.error(f"Error al leer Materiales: {e}")
        else:
            st.info("Esperando archivo…")
        st.markdown('</div>', unsafe_allow_html=True)

    col3, col4 = st.columns(2)

    # Clientes
    with col3:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 👥 Maestro de clientes")
        f3 = st.file_uploader("Subir Clientes", type=["xlsx"], key="u3", label_visibility="collapsed")
        if f3:
            try:
                df_cli = pd.read_excel(f3)
                guardar_archivo(f3, "maestro_clientes")
                st.session_state.df_cli = df_cli.copy()
                st.success("✅ Cargado")
                st.dataframe(df_cli, use_container_width=True, height=400)
            except Exception as e:
                st.error(f"Error al leer Clientes: {e}")
        else:
            st.info("Esperando archivo…")
        st.markdown('</div>', unsafe_allow_html=True)

    # Demanda
    with col4:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 📈 Demanda")
        f4 = st.file_uploader("Subir Demanda", type=["xlsx"], key="u4", label_visibility="collapsed")
        if f4:
            try:
                df_dem = pd.read_excel(f4)
                guardar_archivo(f4, "demanda")
                st.session_state.df_dem = df_dem.copy()
                st.success("✅ Cargado")
                st.dataframe(df_dem, use_container_width=True, height=400)
            except Exception as e:
                st.error(f"Error al leer Demanda: {e}")
        else:
            st.info("Esperando archivo…")
        st.markdown('</div>', unsafe_allow_html=True)

# =========================
# TAB 2 — EJECUCIÓN + REAJUSTE
# =========================
with tab2:
    # Recuperamos DataFrames (cargados en Tab 1)
    df_cap = st.session_state.get("df_cap", None)
    df_mat = st.session_state.get("df_mat", None)
    df_cli = st.session_state.get("df_cli", None)
    df_dem = st.session_state.get("df_dem", None)

    if any(x is None for x in [df_cap, df_mat, df_cli, df_dem]):
        st.warning("⚠️ Por favor, carga los 4 archivos en la pestaña anterior para habilitar los ajustes.")
        st.stop()

    # Limpieza de columnas
    for d in [df_cap, df_mat, df_cli, df_dem]:
        d.columns = d.columns.str.strip()

    # -----------------------------
    # Función local: Generación inicial (usa el planificador por lotes)
    # -----------------------------
    def ejecutar_modoC_base(df_cap, df_mat, df_cli, df_dem):
        capacidades = leer_capacidades(df_cap)
        DG_code, MCH_code, _ = detectar_centros_desde_capacidades(capacidades)

        # Normalización fechas y semana (ISO con 'W')
        df_dem = df_dem.copy()
        df_dem["Fecha_DT"] = pd.to_datetime(df_dem["Fecha de necesidad"])
        iso = df_dem["Fecha_DT"].dt.isocalendar()
        df_dem["Semana_Label"] = iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)

        # Merge con maestros
        col_cli_dem = detectar_columna_cliente(df_dem)
        col_cli_cli = detectar_columna_cliente(df_cli)
        if not col_cli_dem or not col_cli_cli:
            st.error("❌ No se encontró la columna de cliente en Demanda o Clientes.")
            st.stop()

        df = df_dem.merge(df_mat, on=["Material", "Unidad"], how="left")
        df = df.merge(df_cli, left_on=col_cli_dem, right_on=col_cli_cli, how="left")

        # Decisión por coste
        COL_COST_DG = next((c for c in df.columns if "dg" in c.lower() and "cost" in c.lower()), None)
        COL_COST_MCH = next((c for c in df.columns if "mch" in c.lower() and "cost" in c.lower()), None)

        def decidir_centro(r):
            c1 = to_float_safe(r.get(COL_COST_DG, 0))
            c2 = to_float_safe(r.get(COL_COST_MCH, 0))
            return DG_code if c1 < c2 else MCH_code

        df["Centro_Base"] = df.apply(decidir_centro, axis=1)

        # Agrupar demanda base
        g = df.groupby(
            ["Material","Unidad","Centro_Base","Fecha de necesidad","Semana_Label"], dropna=False
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
        g["Centro"] = g["Centro"].apply(norm_code)
        g["Lote_min"] = g["Tamaño lote mínimo"]
        g["Lote_max"] = g["Tamaño lote máximo"]

        # Generación inicial de propuestas (planificador por lotes con capacidad)
        df_c = modo_C(
            df_agr=g[["Material","Unidad","Centro","Cantidad","Fecha","Semana","Lote_min","Lote_max"]],
            df_mat=df_mat,
            capacidades=capacidades,
            DG_code=DG_code, MCH_code=MCH_code
        )

        # Calcular horas
        tiempos = df_mat[["Material","Unidad","Tiempo fabricación unidad DG","Tiempo fabricación unidad MCH"]].drop_duplicates()
        df_c = df_c.merge(tiempos, on=["Material","Unidad"], how="left")
        df_c["Horas"] = np.where(
            df_c["Centro"].astype(str) == str(DG_code),
            df_c["Cantidad a fabricar"] * df_c["Tiempo fabricación unidad DG"],
            df_c["Cantidad a fabricar"] * df_c["Tiempo fabricación unidad MCH"]
        )

        return df_c, capacidades, DG_code, MCH_code

    # -----------------------------
    # Función local: Reajuste semanal + Replanificación
    # -----------------------------
    def replanificar_con_porcentajes(df_base, df_mat, capacidades, DG_code, MCH_code, ajustes):
        # 1) Reparto por semana (en HORAS)
        df_repartido = []
        for sem in sorted(df_base["Semana"].dropna().astype(str).unique().tolist()):
            df_sem = df_base[df_base["Semana"].astype(str) == sem].copy()
            if df_sem.empty:
                continue
            pct = ajustes.get(sem, 50)
            df_sem = repartir_porcentaje(df_sem, pct, DG_code, MCH_code)
            df_repartido.append(df_sem)

        df_adj = pd.concat(df_repartido, ignore_index=True) if df_repartido else df_base.copy()

        # 2) Replanificación
        df_adj_pre = df_adj.rename(columns={"Cantidad a fabricar":"Cantidad"})[
            ["Material","Unidad","Centro","Cantidad","Fecha","Semana","Lote_min","Lote_max"]
        ]
        df_final = modo_C(df_adj_pre, df_mat, capacidades, DG_code, MCH_code)

        # 3) Recalcular Horas
        tiempos = df_mat[["Material","Unidad","Tiempo fabricación unidad DG","Tiempo fabricación unidad MCH"]].drop_duplicates()
        df_final = df_final.merge(tiempos, on=["Material","Unidad"], how="left")
        df_final["Horas"] = np.where(
            df_final["Centro"].astype(str) == str(DG_code),
            df_final["Cantidad a fabricar"] * df_final["Tiempo fabricación unidad DG"],
            df_final["Cantidad a fabricar"] * df_final["Tiempo fabricación unidad MCH"]
        )

        return df_final

    # -----------------------------
    # UI — Paso 1: Generación inicial
    # -----------------------------
    st.subheader("🚀 Generación inicial de la planificación")

    if st.button("🚀 EJECUTAR CÁLCULO DE PROPUESTA", use_container_width=True):
        with st.spinner("Generando planificación inicial…"):
            df_base, capacidades, DG, MCH = ejecutar_modoC_base(df_cap, df_mat, df_cli, df_dem)

        st.session_state.calculo_realizado = True
        st.session_state.df_base = df_base
        st.session_state.capacidades = capacidades
        st.session_state.DG = DG
        st.session_state.MCH = MCH

        st.success("✅ Cálculo inicial completado con éxito.")

    # -----------------------------
    # Utilidad para mostrar y descargar sin columnas ocultas
    # -----------------------------
    def mostrar_detalle_y_descargar(df, nombre_descarga):
        # Columnas visibles (sin Semana, Lote_min, Lote_max)
        cols_visibles = [
            "Nº de propuesta","Material","Centro","Clase de orden",
            "Cantidad a fabricar","Unidad","Fecha"
        ]
        cols_presentes = [c for c in cols_visibles if c in df.columns]

        # Tabla en pantalla
        st.dataframe(df[cols_presentes], use_container_width=True, height=420)

        # Excel sin las columnas ocultas
        output_path = os.path.join(UPLOAD_DIR, f"{nombre_descarga}_{datetime.now().strftime('%Y%m%d')}.xlsx")
        try:
            df[cols_presentes].to_excel(output_path, index=False)
            with open(output_path, "rb") as f:
                st.download_button(
                    f"📥 Descargar {nombre_descarga} (Excel)",
                    data=f,
                    file_name=f"{nombre_descarga}_{datetime.now().strftime('%Y%m%d')}.xlsx"
                )
        except Exception as e:
            st.info(f"No se pudo generar el Excel: {e}")

    # -----------------------------
    # Mostrar resultados del cálculo inicial
    # -----------------------------
    if st.session_state.get("calculo_realizado", False):
        df_base = st.session_state.df_base
        DG = st.session_state.DG
        MCH = st.session_state.MCH

        # Métricas (opcionales y ligeras)
        total_props = len(df_base)
        horas_por_centro = df_base.groupby("Centro")["Horas"].sum().to_dict()

        m = st.columns(3)
        m[0].metric("Total Propuestas (inicial)", f"{total_props:,}".replace(",", "."))
        m[1].metric(f"Horas totales {DG}", f"{horas_por_centro.get(DG, 0):,.1f}h".replace(",", "."))
        m[2].metric(f"Horas totales {MCH}", f"{horas_por_centro.get(MCH, 0):,.1f}h".replace(",", "."))

        # Distribución semanal de carga (inicial)
        st.subheader("📊 Distribución de Carga Horaria (semanal)")
        df_base_plot = df_base.copy()
        df_base_plot["Centro"] = df_base_plot["Centro"].astype(str)
        df_base_plot["Semana"] = df_base_plot["Semana"].astype(str)   # <-- fuerza 'W' como texto
        carga_plot_ini = (
            df_base_plot.groupby(["Semana", "Centro"])["Horas"]
                        .sum()
                        .unstack()
                        .fillna(0)
                        .sort_index()
        )
        col_order = [str(DG), str(MCH)]
        carga_plot_ini = carga_plot_ini.reindex(columns=[c for c in col_order if c in carga_plot_ini.columns])
        st.bar_chart(carga_plot_ini, use_container_width=True)
        st.caption("Resumen semanal de horas por centro (inicial)")
        st.dataframe(carga_plot_ini.style.format("{:,.1f}"), use_container_width=True)

        st.markdown("---")
        st.subheader("📋 Detalle de la Propuesta (inicial)")
        mostrar_detalle_y_descargar(df_base, "Propuesta_Inicial")

        st.markdown("---")
        st.subheader("🔁 ¿Quieres reajustar por semana y re‑planificar?")

        # Botón que habilita los sliders por semana
        if st.button("Reajustar y volver a planificar por semana", use_container_width=True):
            st.session_state.mostrar_reajuste = True

        # Sliders + Replanificación
        if st.session_state.get("mostrar_reajuste", False):
            lista_semanas = sorted(df_base["Semana"].dropna().astype(str).unique())
            st.markdown("**Configura los porcentajes por semana (0% = MCH · 100% = DG)**")
            ajustes = {}
            cols_sliders = st.columns(4)
            for i, sem in enumerate(lista_semanas):
                with cols_sliders[i % 4]:
                    ajustes[sem] = st.slider(f"Sem {sem}", 0, 100, 50, key=f"slider_{sem}")

            st.info("Pulsa **Aplicar porcentajes** para re‑planificar.")
            if st.button("Aplicar porcentajes y re‑planificar", use_container_width=True):
                with st.spinner("Aplicando reparto y re‑planificando…"):
                    df_final = replanificar_con_porcentajes(
                        df_base=st.session_state.df_base,
                        df_mat=st.session_state.df_mat,
                        capacidades=st.session_state.capacidades,
                        DG_code=st.session_state.DG,
                        MCH_code=st.session_state.MCH,
                        ajustes=ajustes
                    )
                st.session_state.df_final_reajuste = df_final
                st.success("✅ Re‑planificación completada.")

        # Resultados finales tras reajuste
        if st.session_state.get("df_final_reajuste", None) is not None:
            df_final = st.session_state.df_final_reajuste

            # Métricas finales
            st.markdown("---")
            st.subheader("📈 Resultados tras Re‑planificación")
            horas_por_centro_final = df_final.groupby("Centro")["Horas"].sum().to_dict()
            m2 = st.columns(3)
            m2[0].metric("Total Propuestas (reajuste)", f"{len(df_final):,}".replace(",", "."))
            m2[1].metric(f"Horas totales {DG}", f"{horas_por_centro_final.get(DG, 0):,.1f}h".replace(",", "."))
            m2[2].metric(f"Horas totales {MCH}", f"{horas_por_centro_final.get(MCH, 0):,.1f}h".replace(",", "."))

            # Distribución semanal de carga (re‑planificada)
            st.subheader("📊 Distribución de Carga Horaria (semanal) — Re‑planificación")
            df_final_plot = df_final.copy()
            df_final_plot["Centro"] = df_final_plot["Centro"].astype(str)
            df_final_plot["Semana"] = df_final_plot["Semana"].astype(str)   # <-- fuerza 'W' como texto
            carga_plot_fin = (
                df_final_plot.groupby(["Semana", "Centro"])["Horas"]
                             .sum()
                             .unstack()
                             .fillna(0)
                             .sort_index()
            )
            col_order = [str(DG), str(MCH)]
            carga_plot_fin = carga_plot_fin.reindex(columns=[c for c in col_order if c in carga_plot_fin.columns])
            st.bar_chart(carga_plot_fin, use_container_width=True)
            st.caption("Resumen semanal de horas por centro (re‑planificado)")
            st.dataframe(carga_plot_fin.style.format("{:,.1f}"), use_container_width=True)

            # Tabla y descarga final (sin Semana/Lote_min/Lote_max)
            st.subheader("📋 Detalle de la Propuesta (reajustada)")
            mostrar_detalle_y_descargar(df_final, "Propuesta_Replan")

# Footer — Texto centrado con mensaje solicitado
st.markdown("---")
st.markdown("""
<div class="footer">
    <p>
        <strong>Carga los 4 archivos Excel necesarios</strong>, se ejecutará una primera planificación y, 
        en caso de ser necesario, ajusta los porcentajes por semana y genera la planificación completa.
    </p>
</div>
""", unsafe_allow_html=True)
