import streamlit as st
import pandas as pd
import numpy as np
import os
import math
from datetime import datetime

# ==========================================
# CONFIGURACIÓN GENERAL
# ==========================================
st.set_page_config(
    page_title="Sistema de Cálculo de Fabricación",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    h1 { color: #1f77b4; text-align: center; }
    h2 { color: #2c3e50; border-bottom: 3px solid #1f77b4; padding-bottom: 4px; }
    .section-container {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border-left: 5px solid #1f77b4;
        margin-bottom: 1.5rem;
    }
    .footer {
        text-align: center; color: #7f8c8d; font-size: 13px; margin-top: 2rem;
        padding-top: 1rem; border-top: 1px solid #ccc;
    }
    </style>
""", unsafe_allow_html=True)

# Crear carpeta para guardar archivos
UPLOAD_DIR = "archivos_cargados"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)


# ==========================================
# GUARDAR ARCHIVOS
# ==========================================
def guardar_archivo(archivo, nombre):
    if archivo is None:
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta = os.path.join(UPLOAD_DIR, f"{nombre}_{ts}.xlsx")
    with open(ruta, "wb") as f:
        f.write(archivo.getbuffer())
    return ruta


# ==========================================
# PROCESO PRINCIPAL (FIX COMPLETO)
# ==========================================
def procesar_logica_estable(df_dem, df_mat, df_cli, df_cap, ajustes_semanales):

    # Centros
    lista_centros = df_cap["Centro"].astype(str).unique().tolist()
    C1 = lista_centros[0]     # DG
    C2 = lista_centros[1]     # MCH

    PRECIO_KM = 0.15

    # Fechas
    df_dem["Fecha_DT"] = pd.to_datetime(df_dem["Fecha de necesidad"])
    df_dem["Semana_Label"] = df_dem["Fecha_DT"].dt.strftime("%Y-W%U")

    # Merge
    df = df_dem.merge(df_mat, on=["Material", "Unidad"], how="left")
    df = df.merge(df_cli, on="Cliente", how="left")

    # Crear diccionario de columnas normalizadas
    cols_lower = {c.lower().strip(): c for c in df.columns}

    def pick(*names):
        for name in names:
            n = name.lower().strip()
            if n in cols_lower:
                return cols_lower[n]
        return None

    # Columnas reales del Excel
    dist_DG = pick("distancia a dg", "distáncia a dg", "dist dg")
    dist_MCH = pick("distancia a mch", "distáncia a mch", "dist mch")
    cost_DG = pick("coste del envío dg", "coste envio dg", "precio km dg", "costekm dg")
    cost_MCH = pick("coste del envío mch", "coste envio mch", "precio km mch", "costekm mch")

    # ======================================
    # FUNCIÓN DE DECISIÓN DE CENTRO (FIX)
    # ======================================
    def decidir_centro(r):

        # Exclusivos
        if str(r.get("Exclusico DG", r.get("Exclusivo DG", ""))).strip().upper() == "X":
            return C1
        if str(r.get("Exclusivo MCH", "")).strip().upper() == "X":
            return C2

        # Distancias reales
        d1 = float(r.get(dist_DG, 0) or 0)
        d2 = float(r.get(dist_MCH, 0) or 0)

        # Coste por km real
        p1 = float(r.get(cost_DG, PRECIO_KM) or PRECIO_KM)
        p2 = float(r.get(cost_MCH, PRECIO_KM) or PRECIO_KM)

        # Fabricación
        cf1 = float(r.get("Coste fabricacion unidad DG", 0) or 0)
        cf2 = float(r.get("Coste fabricacion unidad MCH", 0) or 0)

        cant = float(r.get("Cantidad", 0) or 0)

        coste1 = d1 * p1 + cant * cf1
        coste2 = d2 * p2 + cant * cf2

        if coste1 < coste2:
            return C1
        if coste2 < coste1:
            return C2

        # Empate
        rng = np.random.RandomState(r.name)
        umbral = ajustes_semanales.get(r["Semana_Label"], 50) / 100
        return C1 if rng.rand() < umbral else C2

    df["Centro_Final"] = df.apply(decidir_centro, axis=1)

    # Agrupar por fecha (día)
    df_g = df.groupby(
        ["Material", "Unidad", "Centro_Final", "Fecha de necesidad", "Semana_Label"]
    ).agg({
        "Cantidad": "sum",
        "Tamaño lote mínimo": "first",
        "Tamaño lote máximo": "first",
        "Tiempo fabricación unidad DG": "first",
        "Tiempo fabricación unidad MCH": "first"
    }).reset_index()

    # ======================================
    # CAPACIDAD DIARIA (FIX REAL)
    # ======================================
    horas_col = None
    for c in df_cap.columns:
        if "hora" in c.lower() or "capacidad" in c.lower():
            horas_col = c
            break

    if horas_col:
        base_cap = df_cap.groupby("Centro")[horas_col].sum().to_dict()
    else:
        base_cap = {C1: float("inf"), C2: float("inf")}

    fechas = sorted(pd.to_datetime(df_g["Fecha de necesidad"]).dt.normalize().unique())

    capacidad_restante = {
        (centro, fecha): base_cap[centro]
        for centro in base_cap
        for fecha in fechas
    }

    # ======================================
    # GENERACIÓN ORDENES
    # ======================================
    resultado = []
    cont = 1

    for _, fila in df_g.iterrows():

        fecha = pd.to_datetime(fila["Fecha de necesidad"]).normalize()
        semana = fila["Semana_Label"]
        pref = fila["Centro_Final"]

        cant = max(float(fila["Cantidad"]), float(fila["Tamaño lote mínimo"]))
        max_lote = float(fila["Tamaño lote máximo"])
        num_lotes = math.ceil(cant / max_lote)
        tam_lote = round(cant / num_lotes, 2)

        t_dg = float(fila["Tiempo fabricación unidad DG"])
        t_mch = float(fila["Tiempo fabricación unidad MCH"])

        def horas(c):
            return tam_lote * (t_dg if c == C1 else t_mch)

        for _ in range(num_lotes):

            centro = pref
            h_pref = horas(centro)

            clave_pref = (centro, fecha)

            if capacidad_restante.get(clave_pref, -1) >= h_pref:
                capacidad_restante[clave_pref] -= h_pref
                sin_cap = False
            else:
                otro = C2 if centro == C1 else C1
                h_otro = horas(otro)
                clave_otro = (otro, fecha)

                if capacidad_restante.get(clave_otro, -1) >= h_otro:
                    centro = otro
                    capacidad_restante[clave_otro] -= h_otro
                    sin_cap = False
                else:
                    sin_cap = True

            tiempo = tam_lote * (t_dg if centro == C1 else t_mch)

            resultado.append({
                "Nº de propuesta": cont,
                "Material": fila["Material"],
                "Centro": centro,
                "Clase de orden": "NORM",
                "Cantidad a fabricar": tam_lote,
                "Unidad": fila["Unidad"],
                "Fecha de fabricación": fecha.strftime("%Y%m%d"),
                "Semana": semana,
                "Horas": tiempo,
                "Sin capacidad (informativo)": sin_cap
            })

            cont += 1

    return pd.DataFrame(resultado)



# ==========================================
# INTERFAZ COMPLETA (NO TOCADA)
# ==========================================
st.markdown("<h1>📊 Sistema de Cálculo de Fabricación</h1>", unsafe_allow_html=True)
st.markdown("Carga los 4 archivos Excel necesarios y ajusta los parámetros de ejecución.")
st.markdown("---")

tab1, tab2 = st.tabs(["📥 Carga de Archivos", "⚙️ Ajuste y Ejecución"])

df_cap = df_mat = df_cli = df_dem = None


# --- TAB 1 ---
with tab1:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 🏭 Capacidad de planta")
        f1 = st.file_uploader("Subir Capacidad", type=["xlsx"], key="cap", label_visibility="collapsed")
        if f1:
            df_cap = pd.read_excel(f1)
            guardar_archivo(f1, "capacidad")
            st.success("✔ Cargado")
            st.dataframe(df_cap)
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 📦 Maestro de materiales")
        f2 = st.file_uploader("Subir Materiales", type=["xlsx"], key="mat", label_visibility="collapsed")
        if f2:
            df_mat = pd.read_excel(f2)
            guardar_archivo(f2, "materiales")
            st.success("✔ Cargado")
            st.dataframe(df_mat)
        st.markdown('</div>', unsafe_allow_html=True)

    col3, col4 = st.columns(2)

    with col3:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 👥 Maestro de clientes")
        f3 = st.file_uploader("Subir Clientes", type=["xlsx"], key="cli", label_visibility="collapsed")
        if f3:
            df_cli = pd.read_excel(f3)
            guardar_archivo(f3, "clientes")
            st.success("✔ Cargado")
            st.dataframe(df_cli)
        st.markdown('</div>', unsafe_allow_html=True)

    with col4:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 📈 Demanda")
        f4 = st.file_uploader("Subir Demanda", type=["xlsx"], key="dem", label_visibility="collapsed")
        if f4:
            df_dem = pd.read_excel(f4)
            guardar_archivo(f4, "demanda")
            st.success("✔ Cargado")
            st.dataframe(df_dem)
        st.markdown('</div>', unsafe_allow_html=True)


# --- TAB 2 ---
with tab2:
    if df_cap is None or df_mat is None or df_cli is None or df_dem is None:
        st.warning("⚠️ Carga los 4 archivos para continuar.")
    else:
        df_dem["Semana_Label"] = pd.to_datetime(df_dem["Fecha de necesidad"]).dt.strftime("%Y-W%U")
        semanas = sorted(df_dem["Semana_Label"].unique())

        st.subheader("⚙️ Configuración de Porcentajes por Semana")
        ajustes = {}
        cols = st.columns(4)

        for i, sem in enumerate(semanas):
            with cols[i % 4]:
                ajustes[sem] = st.slider(f"Semana {sem}", 0, 100, 50)

        if st.button("🚀 EJECUTAR CÁLCULO DE PROPUESTA", use_container_width=True):
            df_res = procesar_logica_estable(df_dem, df_mat, df_cli, df_cap, ajustes)

            st.success("✔ Cálculo completado")
            st.dataframe(df_res.drop(columns=["Horas"]), use_container_width=True)

            ruta = os.path.join(UPLOAD_DIR, "Propuesta_Final.xlsx")
            df_res.drop(columns=["Semana", "Horas"]).to_excel(ruta, index=False)

            with open(ruta, "rb") as f:
                st.download_button(
                    "📥 Descargar Propuesta",
                    f,
                    file_name=f"Propuesta_Fabricacion_{datetime.now().strftime('%Y%m%d')}.xlsx"
                )


# FOOTER
st.markdown("""
<div class="footer">
Sistema de Cálculo de Fabricación — 2026
</div>
""", unsafe_allow_html=True)
