import streamlit as st
import pandas as pd
import numpy as np
import os
import math
from datetime import datetime, timedelta

# Configuración de página
st.set_page_config(
    page_title="Sistema de Cálculo de Fabricación",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# ESTILOS
# ==========================================
st.markdown("""
    <style>
    .main { padding-top: 2rem; }
    h1 { color: #1f77b4; text-align: center; }
    h2 { color: #2c3e50; border-bottom: 3px solid #1f77b4; padding-bottom: .3rem; }
    .section-container {
        background-color: #f8f9fa; padding: 1rem;
        border-radius: 10px; border-left: 5px solid #1f77b4; margin-bottom: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# FUNCIONES AUXILIARES
# ==========================================
UPLOAD_DIR = "archivos_cargados"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

def guardar_archivo(archivo, nombre):
    if archivo is None:
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta = os.path.join(UPLOAD_DIR, f"{nombre}_{ts}.xlsx")
    with open(ruta, "wb") as f:
        f.write(archivo.getbuffer())
    return ruta


# ==========================================
#   LOGICA PRINCIPAL (MODO C)
# ==========================================
def procesar_logica_estable(df_dem, df_mat, df_cli, df_cap, ajustes):

    # ------------- UTILIDAD CONVERSIÓN NUMÉRICA ----------------
    def to_float(v):
        if pd.isna(v):
            raise ValueError("⚠️ Error: Valor numérico vacío detectado en un campo crítico.")
        if isinstance(v, str):
            v = v.replace(",", ".").strip()
        return float(v)

    # ------------- DETECTAR CENTROS DG/MCH ----------------
    centros = [str(c) for c in df_cap["Centro"].astype(str).unique()]
    DG = next((c for c in centros if c.endswith("833")), centros[0])
    MCH = next((c for c in centros if c.endswith("184")), centros[-1])

    # Centro preferido por código
    C1, C2 = DG, MCH

    # ------------- PREPARAR DATA ----------------
    df_dem["Fecha_DT"] = pd.to_datetime(df_dem["Fecha de necesidad"])
    df_dem["Semana_Label"] = df_dem["Fecha_DT"].dt.strftime("%Y-W%U")

    df = df_dem.merge(df_mat, on=["Material","Unidad"], how="left")
    df = df.merge(df_cli, on="Cliente", how="left")

    # Columnas EXACTAS del Excel (las que tú tienes)
    COL_DIST_DG  = "Distáncia a DG"
    COL_DIST_MCH = "Distáncia a MCH"
    COL_COST_DG  = "Coste del envío DG"
    COL_COST_MCH = "Coste del envío MCH"
    COL_CU_DG = "Coste unitario DG"
    COL_CU_MCH = "Coste unitario MCH"

    # ------------- DECISIÓN DE CENTRO (COSTE REAL) ----------------
    def decidir_centro(r):

        # Exclusivos
        if str(r.get("Exclusico DG","")).upper() == "X":
            return C1
        if str(r.get("Exclusivo MCH","")).upper() == "X":
            return C2

        dist_dg  = to_float(r[COL_DIST_DG])
        dist_mch = to_float(r[COL_DIST_MCH])
        pk_dg    = to_float(r[COL_COST_DG])
        pk_mch   = to_float(r[COL_COST_MCH])
        cu_dg    = to_float(r[COL_CU_DG])
        cu_mch   = to_float(r[COL_CU_MCH])
        qty      = to_float(r["Cantidad"])

        coste_dg  = dist_dg  * pk_dg  + qty * cu_dg
        coste_mch = dist_mch * pk_mch + qty * cu_mch

        if coste_dg < coste_mch: return C1
        if coste_mch < coste_dg: return C2

        rng = np.random.RandomState(r.name)
        return C1 if rng.rand() < ajustes.get(r["Semana_Label"],50)/100 else C2

    df["Centro_Final"] = df.apply(decidir_centro, axis=1)

    # ------------- AGRUPACIÓN ----------------
    df_agr = df.groupby(
        ["Material","Unidad","Centro_Final","Fecha de necesidad","Semana_Label"]
    ).agg({
        "Cantidad":"sum",
        "Tamaño lote mínimo":"first",
        "Tamaño lote máximo":"first",
        "Tiempo fabricación unidad DG":"first",
        "Tiempo fabricación unidad MCH":"first"
    }).reset_index()

    # ------------- CAPACIDAD DIARIA ----------------
    horas_col = next((c for c in df_cap.columns if "hora" in c.lower()), None)
    if horas_col is None:
        base_cap = {C1: float("inf"), C2: float("inf")}
    else:
        base_cap = df_cap.groupby("Centro")[horas_col].sum().to_dict()

    capacidad_restante = {}

    def get_cap(centro, fecha):
        clave = (str(centro), fecha)
        if clave not in capacidad_restante:
            capacidad_restante[clave] = float(base_cap.get(str(centro),0))
        return capacidad_restante[clave]

    def consume(centro, fecha, horas):
        clave = (str(centro), fecha)
        capacidad_restante[clave] = get_cap(centro, fecha) - horas

    # =============================================
    #           PRODUCCIÓN MODO C:
    #   SI NO CABE → MOVER AL DÍA SIGUIENTE
    # =============================================
    resultado = []
    cont = 1

    for _, fila in df_agr.iterrows():

        fecha_actual = pd.to_datetime(fila["Fecha de necesidad"]).normalize()
        semana = fila["Semana_Label"]
        pref = fila["Centro_Final"]

        total = max(to_float(fila["Cantidad"]), to_float(fila["Tamaño lote mínimo"]))
        lotemax = max(1, to_float(fila["Tamaño lote máximo"]))

        t_dg  = to_float(fila["Tiempo fabricación unidad DG"])
        t_mch = to_float(fila["Tiempo fabricación unidad MCH"])

        def horas(centro, qty):
            return qty * (t_dg if centro==C1 else t_mch)

        def qty_segun_cap(centro, cap):
            time_unit = t_dg if centro==C1 else t_mch
            if time_unit <= 0: return 0
            return cap / time_unit

        restante_global = total

        # Troceo por tamaño lote máximo
        lotes = []
        while restante_global > 0:
            q = round(min(restante_global, lotemax), 2)
            lotes.append(q)
            restante_global = round(restante_global - q, 6)

        # Procesar cada lote en modo C
        for qlote in lotes:

            restante = qlote

            while restante > 0:

                cap_dia = get_cap(pref, fecha_actual)
                h_neces = horas(pref, restante)

                if cap_dia >= h_neces:
                    # Cabe entero hoy
                    consume(pref, fecha_actual, h_neces)
                    resultado.append({
                        "Nº de propuesta": cont,
                        "Material": fila["Material"],
                        "Centro": pref,
                        "Clase de orden": "NORM",
                        "Cantidad a fabricar": round(restante,2),
                        "Unidad": fila["Unidad"],
                        "Fecha de fabricación": fecha_actual.strftime("%Y%m%d"),
                        "Semana": semana,
                        "Horas": h_neces,
                        "Sin capacidad (informativo)": False
                    })
                    cont += 1
                    restante = 0

                else:
                    # No cabe entero → producir parte
                    qpos = round(qty_segun_cap(pref, cap_dia), 2)

                    if qpos > 0:
                        h_prod = horas(pref, qpos)
                        consume(pref, fecha_actual, h_prod)

                        resultado.append({
                            "Nº de propuesta": cont,
                            "Material": fila["Material"],
                            "Centro": pref,
                            "Clase de orden": "NORM",
                            "Cantidad a fabricar": qpos,
                            "Unidad": fila["Unidad"],
                            "Fecha de fabricación": fecha_actual.strftime("%Y%m%d"),
                            "Semana": semana,
                            "Horas": h_prod,
                            "Sin capacidad (informativo)": False
                        })
                        cont += 1
                        restante = round(restante - qpos, 6)

                    # MOVER EL RESTO AL DÍA SIGUIENTE
                    if restante > 0:
                        fecha_actual = fecha_actual + timedelta(days=1)
                        semana = fecha_actual.strftime("%Y-W%U")

    return pd.DataFrame(resultado)


# ==========================================
# INTERFAZ
# ==========================================
st.markdown("<h1>📊 Sistema de Cálculo de Fabricación</h1>", unsafe_allow_html=True)
st.markdown("Carga los 4 archivos Excel y ejecuta el cálculo (Modo C).")
st.markdown("---")

tab1, tab2 = st.tabs(["📥 Carga de Archivos", "⚙️ Ejecución"])

df_cap = df_mat = df_cli = df_dem = None

# --- TAB 1 ---
with tab1:

    st.subheader("Carga de Datos")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### Capacidad")
        f1 = st.file_uploader("Subir Capacidad", type=["xlsx"], key="cap")
        if f1:
            df_cap = pd.read_excel(f1)
            guardar_archivo(f1, "capacidad")
            st.success("✔ Cargado")
            st.dataframe(df_cap)
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### Materiales")
        f2 = st.file_uploader("Subir Materiales", type=["xlsx"], key="mat")
        if f2:
            df_mat = pd.read_excel(f2)
            guardar_archivo(f2, "materiales")
            st.success("✔ Cargado")
            st.dataframe(df_mat)
        st.markdown('</div>', unsafe_allow_html=True)

    col3, col4 = st.columns(2)

    with col3:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### Clientes")
        f3 = st.file_uploader("Subir Clientes", type=["xlsx"], key="cli")
        if f3:
            df_cli = pd.read_excel(f3)
            guardar_archivo(f3, "clientes")
            st.success("✔ Cargado")
            st.dataframe(df_cli)
        st.markdown('</div>', unsafe_allow_html=True)

    with col4:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### Demanda")
        f4 = st.file_uploader("Subir Demanda", type=["xlsx"], key="dem")
        if f4:
            df_dem = pd.read_excel(f4)
            guardar_archivo(f4, "demanda")
            st.success("✔ Cargado")
            st.dataframe(df_dem)
        st.markdown('</div>', unsafe_allow_html=True)


# --- TAB 2 ---
with tab2:
    if any(df is None for df in [df_cap, df_mat, df_cli, df_dem]):
        st.warning("⚠️ Debes cargar los 4 archivos antes de ejecutar.")
    else:

        df_dem["Semana_Label"] = pd.to_datetime(df_dem["Fecha de necesidad"]).dt.strftime("%Y-W%U")
        semanas = sorted(df_dem["Semana_Label"].unique())

        st.subheader("⚙️ Configuración empates")
        ajustes = {w: st.slider(w, 0, 100, 50) for w in semanas}

        if st.button("🚀 Ejecutar (Modo C)", use_container_width=True):

            with st.spinner("Calculando..."):
                df_res = procesar_logica_estable(df_dem, df_mat, df_cli, df_cap, ajustes)

            st.success("✔ Cálculo completado")
            st.dataframe(df_res.drop(columns=["Horas"]), use_container_width=True)

            out = os.path.join(UPLOAD_DIR, "Propuesta_Modo_C.xlsx")
            df_res.drop(columns=["Semana","Horas"]).to_excel(out, index=False)

            with open(out, "rb") as f:
                st.download_button("📥 Descargar Excel", f, file_name="Propuesta_Modo_C.xlsx")


# Footer
st.markdown("""
<div class="footer">
✨ Sistema de Fabricación — Modo C (Mover al día siguiente) — 2026
</div>
""", unsafe_allow_html=True)
