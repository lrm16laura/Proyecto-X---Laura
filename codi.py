# ============================================================
# SISTEMA COMPLETO DE CÁLCULO DE FABRICACIÓN — MODO C + AJUSTE
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

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
# ESTILOS CSS
# ------------------------------------------------------------
st.markdown("""
<style>
.main { padding-top: 2rem; }
h1 { color: #1f77b4; text-align: center; }
h2 { color: #2c3e50; border-bottom: 3px solid #1f77b4; padding-bottom: .3rem; }
.section-container {
    background-color: #f8f9fa; padding: 1rem;
    border-radius: 10px; border-left: 5px solid #1f77b4; margin-bottom: 1rem;
}
.footer { text-align: center; color:#7f8c8d; font-size:13px; margin-top:2rem;
          padding-top:1rem; border-top:1px solid #ccc; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# UTILIDADES
# ------------------------------------------------------------
UPLOAD_DIR = "archivos_cargados"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def guardar_archivo(archivo, nombre):
    if archivo is None:
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta = os.path.join(UPLOAD_DIR, f"{nombre}_{ts}.xlsx")
    with open(ruta, "wb") as f:
        f.write(archivo.getbuffer())
    return ruta


# ------------------------------------------------------------
# REPARTO PROPORCIONAL (PORCENTAJES)
# ------------------------------------------------------------
def repartir_porcentaje(df_semana, pct_dg, dg_code, mch_code):
    """
    Reparte porcentualmente HORAS entre DG y MCH.
    """
    if pct_dg == 0:
        df_semana["Centro"] = mch_code
        return df_semana

    if pct_dg == 100:
        df_semana["Centro"] = dg_code
        return df_semana

    df_semana = df_semana.sort_values("Horas", ascending=False)

    total_h = df_semana["Horas"].sum()
    objetivo = total_h * (pct_dg / 100)

    acumulado = 0
    centros = []

    for _, r in df_semana.iterrows():
        if acumulado < objetivo:
            centros.append(dg_code)
            acumulado += r["Horas"]
        else:
            centros.append(mch_code)

    df_semana["Centro"] = centros
    return df_semana


# ------------------------------------------------------------
# MODO C COMPLETO (con movimiento SOLO dentro del mismo centro)
# ------------------------------------------------------------
def modo_C(df_agrupado, df_cap, df_mat):
    """
    Reaplica toda la lógica del Modo C desde cero.
    Capacidad diaria, división de lotes y movimiento solo al día siguiente.
    """

    # -------------------------
    # Detectar centros
    # -------------------------
    centros = df_cap["Centro"].astype(str).unique().tolist()
    DG = next((c for c in centros if c.endswith("833")), centros[0])
    MCH = next((c for c in centros if c.endswith("184") and c != DG),
               centros[-1] if len(centros) > 1 else centros[0])

    # -------------------------
    # Cargar tiempo por unidad
    # -------------------------
    tiempos = df_mat[["Material", "Unidad",
                      "Tiempo fabricación unidad DG",
                      "Tiempo fabricación unidad MCH"]]

    df = df_agrupado.merge(tiempos, on=["Material", "Unidad"], how="left")

    # -------------------------
    # Capacidad diaria base
    # -------------------------
    horas_col = next((c for c in df_cap.columns
                      if "hora" in c.lower() or "capacidad" in c.lower()), None)

    base = {}
    for centro in centros:
        vals = pd.to_numeric(df_cap.loc[df_cap["Centro"].astype(str) == centro, horas_col],
                             errors="coerce")
        cap = vals.max()
        base[str(centro)] = float(cap if not pd.isna(cap) else 0)

    capacidad_restante = {}

    def get_cap(centro, fecha):
        clave = (str(centro), fecha)
        if clave not in capacidad_restante:
            capacidad_restante[clave] = base[str(centro)]
        return capacidad_restante[clave]

    def consume(centro, fecha, horas):
        capacidad_restante[(str(centro), fecha)] = get_cap(centro, fecha) - horas

    # -------------------------
    # Funciones auxiliares
    # -------------------------
    def tiempo(centro, qty, r):
        if centro == DG:
            return qty * float(r["Tiempo fabricación unidad DG"])
        return qty * float(r["Tiempo fabricación unidad MCH"])

    def q_por_capacidad(centro, cap, r):
        tu = float(r["Tiempo fabricación unidad DG"]) if centro == DG else float(r["Tiempo fabricación unidad MCH"])
        return cap / tu if tu > 0 else 0

    # -------------------------
    # Procesamiento Modo C
    # -------------------------
    out = []
    contador = 1
    MAX_DIAS = 365

    for _, r in df.iterrows():

        centro = r["Centro"]
        fecha = pd.to_datetime(r["Fecha"]).normalize()
        semana = r["Semana"]

        total = float(r["Cantidad"])
        lote_max = float(r["Lote_max"])
        lote_min = float(r["Lote_min"])

        total = max(total, lote_min)

        # Troceo de lotes
        lotes = []
        resto = total
        while resto > 0:
            q = min(resto, lote_max)
            lotes.append(round(q, 2))
            resto = round(resto - q, 6)

        # Para cada lote…
        for ql in lotes:
            pendiente = ql
            dias = 0

            while pendiente > 0:

                caph = get_cap(centro, fecha)
                hnec = tiempo(centro, pendiente, r)

                if caph >= hnec:
                    # Cabe entero
                    consume(centro, fecha, hnec)
                    out.append({
                        "Nº": contador,
                        "Material": r["Material"],
                        "Centro": centro,
                        "Cantidad": round(pendiente, 2),
                        "Unidad": r["Unidad"],
                        "Fecha": fecha.strftime("%d.%m.%Y"),
                        "Semana": semana
                    })
                    contador += 1
                    pendiente = 0
                    break

                # Producir parte
                qpos = q_por_capacidad(centro, caph, r)

                if qpos > 0:
                    hprod = tiempo(centro, qpos, r)
                    consume(centro, fecha, hprod)
                    out.append({
                        "Nº": contador,
                        "Material": r["Material"],
                        "Centro": centro,
                        "Cantidad": round(qpos, 2),
                        "Unidad": r["Unidad"],
                        "Fecha": fecha.strftime("%d.%m.%Y"),
                        "Semana": semana
                    })
                    contador += 1
                    pendiente = round(pendiente - qpos, 6)

                # Si aún queda…
                if pendiente <= 0:
                    break

                # Movernos un día más
                if dias >= MAX_DIAS:
                    out.append({
                        "Nº": contador,
                        "Material": r["Material"],
                        "Centro": centro,
                        "Cantidad": round(pendiente, 2),
                        "Unidad": r["Unidad"],
                        "Fecha": fecha.strftime("%d.%m.%Y"),
                        "Semana": semana
                    })
                    contador += 1
                    pendiente = 0
                    break

                fecha = (fecha + timedelta(days=1)).normalize()
                semana = fecha.strftime("%Y-W%U")
                dias += 1

    return pd.DataFrame(out)


# ------------------------------------------------------------
# PRIMERA EJECUCIÓN DEL MODO C + AJUSTE PORCENTUAL + RE-MODO C
# ------------------------------------------------------------
def ejecutar_calculo(df_cap, df_mat, df_cli, df_dem, ajustes):
    # ----------------------
    # DECISIONES DE COSTE DG/MCH
    # ----------------------
    def to_float(v):
        if pd.isna(v):
            return 0
        if isinstance(v, str):
            v = v.replace(",", ".").strip()
        return float(v)

    centros = [str(c) for c in df_cap["Centro"].astype(str).unique()]
    DG = next((c for c in centros if c.endswith("833")), centros[0])
    MCH = next((c for c in centros if c.endswith("184") and c != DG),
               centros[-1] if len(centros) > 1 else centros[0])

    df_dem["Fecha_DT"] = pd.to_datetime(df_dem["Fecha de necesidad"])
    df_dem["Semana_Label"] = df_dem["Fecha_DT"].dt.strftime("%Y-W%U")

    df = df_dem.merge(df_mat, on=["Material", "Unidad"], how="left")
    df = df.merge(df_cli, on="Cliente", how="left")

    COL_COST_DG = "Coste del envío DG"
    COL_COST_MCH = "Coste del envío MCH"
    COL_CU_DG = "Coste unitario DG"
    COL_CU_MCH = "Coste unitario MCH"

    def decidir(r):
        d1 = to_float(r[COL_COST_DG])
        d2 = to_float(r[COL_COST_MCH])
        cu1 = to_float(r[COL_CU_DG])
        cu2 = to_float(r[COL_CU_MCH])
        q = to_float(r["Cantidad"])

        c1 = d1 + q * cu1
        c2 = d2 + q * cu2

        return DG if c1 < c2 else MCH

    df["Centro_Base"] = df.apply(decidir, axis=1)

    # ----------------------
    # AGRUPACIÓN
    # ----------------------
    g = df.groupby(
        ["Material", "Unidad", "Centro_Base", "Fecha de necesidad", "Semana_Label"]
    ).agg({
        "Cantidad": "sum",
        "Tamaño lote mínimo": "first",
        "Tamaño lote máximo": "first"
    }).reset_index()

    # Renombrar para Modo C
    g = g.rename(columns={
        "Centro_Base": "Centro",
        "Fecha de necesidad": "Fecha",
        "Semana_Label": "Semana",
        "Tamaño lote mínimo": "Lote_min",
        "Tamaño lote máximo": "Lote_max"
    })

    # ----------------------
    # PRIMER MODO C
    # ----------------------
    df_c = modo_C(g, df_cap, df_mat)

    # ----------------------
    # Recalcular horas para reparto
    # ----------------------
    tiempos = df_mat[["Material", "Unidad",
                      "Tiempo fabricación unidad DG",
                      "Tiempo fabricación unidad MCH"]]

    df_c = df_c.merge(tiempos, on=["Material", "Unidad"], how="left")

    df_c["Horas"] = np.where(
        df_c["Centro"] == DG,
        df_c["Cantidad"] * df_c["Tiempo fabricación unidad DG"],
        df_c["Cantidad"] * df_c["Tiempo fabricación unidad MCH"]
    )

    # ----------------------
    # AJUSTE PORCENTUAL SEMANAL
    # ----------------------
    df_final = []

    for sem, pct in ajustes.items():
        df_sem = df_c[df_c["Semana"] == sem].copy()
        df_sem = repartir_porcentaje(df_sem, pct, DG, MCH)
        df_final.append(df_sem)

    df_adj = pd.concat(df_final, ignore_index=True)

    # ----------------------
    # REAPLICAR MODO C DESDE CERO
    # ----------------------
    df_adj = df_adj.rename(columns={
        "Fecha": "Fecha",
        "Lote_min": "Lote_min",
        "Lote_max": "Lote_max"
    })

    df_adj = df_adj[["Material", "Unidad", "Centro", "Cantidad", "Fecha",
                     "Semana", "Lote_min", "Lote_max"]]

    df_modo_C_final = modo_C(df_adj, df_cap, df_mat)

    return df_modo_C_final


# ------------------------------------------------------------
# INTERFAZ DE STREAMLIT
# ------------------------------------------------------------
st.markdown("<h1>📊 Sistema de Cálculo de Fabricación</h1>", unsafe_allow_html=True)

st.markdown("Carga los archivos y ejecuta Modo C + ajuste proporcional + remonte completo de Modo C.")
st.markdown("---")

tab1, tab2 = st.tabs(["📥 Cargar Archivos", "⚙️ Ejecutar"])

df_cap = df_mat = df_cli = df_dem = None

# ============================================================
# TAB 1 — CARGA
# ============================================================
with tab1:

    st.subheader("Carga de Datos")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### Capacidad")
        f1 = st.file_uploader("Subir Capacidad", type=["xlsx"])
        if f1:
            df_cap = pd.read_excel(f1)
            guardar_archivo(f1, "capacidad")
            st.success("✔ Archivo cargado")
            st.dataframe(df_cap)
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### Materiales")
        f2 = st.file_uploader("Subir Materiales", type=["xlsx"])
        if f2:
            df_mat = pd.read_excel(f2)
            guardar_archivo(f2, "materiales")
            st.success("✔ Archivo cargado")
            st.dataframe(df_mat)
        st.markdown("</div>", unsafe_allow_html=True)


    col3, col4 = st.columns(2)

    with col3:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### Clientes")
        f3 = st.file_uploader("Subir Clientes", type=["xlsx"])
        if f3:
            df_cli = pd.read_excel(f3)
            guardar_archivo(f3, "clientes")
            st.success("✔ Archivo cargado")
            st.dataframe(df_cli)
        st.markdown("</div>", unsafe_allow_html=True)

    with col4:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### Demanda")
        f4 = st.file_uploader("Subir Demanda", type=["xlsx"])
        if f4:
            df_dem = pd.read_excel(f4)
            guardar_archivo(f4, "demanda")
            st.success("✔ Archivo cargado")
            st.dataframe(df_dem)
        st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# TAB 2 — EJECUCIÓN
# ============================================================
with tab2:

    if any(x is None for x in [df_cap, df_mat, df_cli, df_dem]):
        st.warning("⚠️ Debes cargar los 4 archivos.")
        st.stop()

    df_dem["Semana_Label"] = pd.to_datetime(df_dem["Fecha de necesidad"]).dt.strftime("%Y-W%U")
    semanas = sorted(df_dem["Semana_Label"].unique())

    st.subheader("Ajuste por semana (0% = MCH / 100% = DG)")
    ajustes = {s: st.slider(s, 0, 100, 50) for s in semanas}

    if st.button("🚀 Ejecutar cálculo", use_container_width=True):

        with st.spinner("Procesando toda la lógica…"):

            df_res = ejecutar_calculo(df_cap, df_mat, df_cli, df_dem, ajustes)

        st.success("✔ Cálculo completado")

        st.dataframe(df_res, use_container_width=True)

        out = os.path.join(UPLOAD_DIR, "Propuesta_Final.xlsx")
        df_res.to_excel(out, index=False)

        with open(out, "rb") as f:
            st.download_button("📥 Descargar Excel", f,
                               file_name="Propuesta_Fabricacion.xlsx")

# Footer
st.markdown("""
<div class="footer">
✨ Sistema de Cálculo de Fabricación — Modo C + Reparto + Re-modo C  
</div>
""", unsafe_allow_html=True)
