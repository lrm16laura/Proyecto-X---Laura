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
# ESTILOS CSS PERSONALIZADOS (Programa 1 + 2)
# ==========================================
st.markdown("""
    <style>
    .main { padding-top: 2rem; }
    h1 { color: #1f77b4; text-align: center; font-size: 2.5rem; margin-bottom: 1rem; }
    h2 { color: #2c3e50; border-bottom: 3px solid #1f77b4; padding-bottom: 0.5rem; }
    .section-container {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #1f77b4;
        margin-bottom: 1.5rem;
    }
    .footer {
        text-align: center; color: #7f8c8d; font-size: 0.9rem; margin-top: 2rem;
        padding-top: 1rem; border-top: 1px solid #ecf0f1;
    }
    .stButton > button { width: 100%; font-weight: bold; border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

# Crear carpeta para guardar archivos si no existe
UPLOAD_DIR = "archivos_cargados"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# ==========================================
# FUNCIONES AUXILIARES Y LÓGICA
# ==========================================

def guardar_archivo(archivo, nombre_seccion):
    if archivo is not None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"{nombre_seccion}_{timestamp}.xlsx"
        ruta_archivo = os.path.join(UPLOAD_DIR, nombre_archivo)
        with open(ruta_archivo, "wb") as f:
            f.write(archivo.getbuffer())
        return ruta_archivo
    return None


# ============================
#      PROCESAR LÓGICA (MODO C)
# ============================
def procesar_logica_estable(df_dem, df_mat, df_cli, df_cap, ajustes_semanales):

    # --- Helper robusto para float ---
    def to_float(v):
        if pd.isna(v):
            raise ValueError("Campo numérico vacío en Excel.")
        if isinstance(v, str):
            v = v.strip().replace(",", ".")
        return float(v)

    # Detectar centros DG/MCH (códigos habituales)
    centros = [str(c).strip() for c in df_cap["Centro"].astype(str).unique()]
    DG = next((c for c in centros if c.endswith("833")), centros[0])
    MCH = next((c for c in centros if c.endswith("184") and c != DG), (centros[1] if len(centros) > 1 else centros[0]))
    C1, C2 = DG, MCH  # C1 = DG, C2 = MCH

    # Preparar demanda
    df_dem["Fecha_DT"] = pd.to_datetime(df_dem["Fecha de necesidad"])
    df_dem["Semana_Label"] = df_dem["Fecha_DT"].dt.strftime("%Y-W%U")

    # Merge
    df = df_dem.merge(df_mat, on=["Material", "Unidad"], how="left")
    df = df.merge(df_cli, on="Cliente", how="left")

    # Columnas reales (según tus Excels)
    COL_DIST_DG  = "Distáncia a DG"
    COL_DIST_MCH = "Distáncia a MCH"
    COL_COST_DG  = "Coste del envío DG"
    COL_COST_MCH = "Coste del envío MCH"
    COL_CU_DG    = "Coste unitario DG"
    COL_CU_MCH   = "Coste unitario MCH"

    # Decidir centro por coste total
    def decidir_centro(r):
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

        coste_dg  = dist_dg * pk_dg + qty * cu_dg
        coste_mch = dist_mch * pk_mch + qty * cu_mch

        if coste_dg < coste_mch:
            return C1
        if coste_mch < coste_dg:
            return C2

        rng = np.random.RandomState(r.name)
        return C1 if rng.rand() < ajustes_semanales.get(r["Semana_Label"],50)/100 else C2

    df["Centro_Final"] = df.apply(decidir_centro, axis=1)

    # Agrupar por día
    df_g = df.groupby(
        ["Material","Unidad","Centro_Final","Fecha de necesidad","Semana_Label"]
    ).agg({
        "Cantidad":"sum",
        "Tamaño lote mínimo":"first",
        "Tamaño lote máximo":"first",
        "Tiempo fabricación unidad DG":"first",
        "Tiempo fabricación unidad MCH":"first"
    }).reset_index()

    # ============================
    # CAPACIDAD DIARIA (del Excel) - valor exacto por centro (sin sumar)
    # ============================
    horas_col = next((c for c in df_cap.columns if "hora" in c.lower() or "capacidad" in c.lower()), None)

    if horas_col:
        base_cap_por_centro = {}
        for centro in df_cap["Centro"].astype(str).unique():
            vals = pd.to_numeric(df_cap.loc[df_cap["Centro"].astype(str)==centro, horas_col], errors="coerce")
            cap = vals.max()
            if pd.isna(cap): cap = 0.0
            base_cap_por_centro[str(centro)] = float(cap)
    else:
        base_cap_por_centro = {C1: float("inf"), C2: float("inf")}

    for c in [C1, C2]:
        if str(c) not in base_cap_por_centro:
            base_cap_por_centro[str(c)] = 0.0

    capacidad_restante = {}

    def get_cap(centro, fecha):
        clave = (str(centro), fecha)
        if clave not in capacidad_restante:
            capacidad_restante[clave] = base_cap_por_centro[str(centro)]
        return capacidad_restante[clave]

    def consume(centro, fecha, horas):
        capacidad_restante[(str(centro), fecha)] = get_cap(centro, fecha) - horas

    # ============================
    #     GENERAR LOTES (Modo C)
    # ============================
    resultado = []
    cont = 1
    MAX_DIAS = 365

    for _, fila in df_g.iterrows():
        fecha_act = pd.to_datetime(fila["Fecha de necesidad"]).normalize()
        semana = fila["Semana_Label"]
        pref = fila["Centro_Final"]

        total = max(to_float(fila["Cantidad"]), to_float(fila["Tamaño lote mínimo"]))
        lotemax = max(1.0, to_float(fila["Tamaño lote máximo"]))

        t_dg = to_float(fila["Tiempo fabricación unidad DG"])
        t_mch = to_float(fila["Tiempo fabricación unidad MCH"])

        def horas(centro, qty):
            return qty * (t_dg if centro==C1 else t_mch)

        def qty_por_cap(centro, cap):
            tu = t_dg if centro==C1 else t_mch
            return cap/tu if tu > 0 else 0.0

        # dividir por tamaño máximo
        resto = total
        lotes = []
        while resto > 0:
            q = min(resto, lotemax)
            lotes.append(round(q, 2))
            resto = round(resto - q, 6)

        # procesar MODO C
        for lote in lotes:
            pendiente = lote
            dias = 0

            # si el centro tiene capacidad base 0 -> no avanzar días
            if base_cap_por_centro.get(str(pref), 0.0) == 0.0:
                h = horas(pref, pendiente)
                resultado.append({
                    "Nº de propuesta": cont,
                    "Material": fila["Material"],
                    "Centro": pref,
                    "Clase de orden": "NORM",
                    "Cantidad a fabricar": round(pendiente, 2),
                    "Unidad": fila["Unidad"],
                    "Fecha de fabricación": fecha_act.strftime('%d.%m.%Y'),
                    "Semana": semana,
                    "Horas": h
                })
                cont += 1
                continue

            while pendiente > 0:

                cap_hoy = get_cap(pref, fecha_act)
                h_neces = horas(pref, pendiente)

                # Cabe entero hoy
                if cap_hoy >= h_neces:
                    consume(pref, fecha_act, h_neces)
                    resultado.append({
                        "Nº de propuesta": cont,
                        "Material": fila["Material"],
                        "Centro": pref,
                        "Clase de orden": "NORM",
                        "Cantidad a fabricar": round(pendiente, 2),
                        "Unidad": fila["Unidad"],
                        "Fecha de fabricación": fecha_act.strftime('%d.%m.%Y'),
                        "Semana": semana,
                        "Horas": h_neces
                    })
                    cont += 1
                    pendiente = 0
                    break

                # Producir parte hoy
                qpos = qty_por_cap(pref, cap_hoy)
                if qpos > 0:
                    h_prod = horas(pref, qpos)
                    consume(pref, fecha_act, h_prod)
                    resultado.append({
                        "Nº de propuesta": cont,
                        "Material": fila["Material"],
                        "Centro": pref,
                        "Clase de orden": "NORM",
                        "Cantidad a fabricar": round(qpos, 2),
                        "Unidad": fila["Unidad"],
                        "Fecha de fabricación": fecha_act.strftime('%d.%m.%Y'),
                        "Semana": semana,
                        "Horas": h_prod
                    })
                    cont += 1
                    pendiente = round(pendiente - qpos, 6)

                    # Si aún queda capacidad hoy -> seguir hoy
                    if get_cap(pref, fecha_act) > 0:
                        continue

                if pendiente <= 0:
                    break

                # Límite de días
                if dias >= MAX_DIAS:
                    h = horas(pref, pendiente)
                    resultado.append({
                        "Nº de propuesta": cont,
                        "Material": fila["Material"],
                        "Centro": pref,
                        "Clase de orden": "NORM",
                        "Cantidad a fabricar": round(pendiente, 2),
                        "Unidad": fila["Unidad"],
                        "Fecha de fabricación": fecha_act.strftime('%d.%m.%Y'),
                        "Semana": semana,
                        "Horas": h
                    })
                    cont += 1
                    pendiente = 0
                    break

                # Pasar al día siguiente
                fecha_act = (fecha_act + timedelta(days=1)).normalize()
                semana = fecha_act.strftime("%Y-W%U")
                dias += 1

    return pd.DataFrame(resultado)

# ==========================================
# INTERFAZ PRINCIPAL
# ==========================================
st.markdown("<h1>📊 Sistema de Cálculo de Fabricación</h1>", unsafe_allow_html=True)
st.markdown("Carga los 4 archivos Excel necesarios y ajusta los parámetros de ejecución.")
st.markdown("---")

tab1, tab2 = st.tabs(["📥 Carga de Archivos", "⚙️ Ajuste y Ejecución"])

df_cap = df_mat = df_cli = df_dem = None

# --- TAB 1 ---
with tab1:
    st.subheader("📁 Carga tus archivos Excel")

    col1, col2 = st.columns(2)

    # Capacidad
    with col1:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 🏭 Capacidad de planta")
        f1 = st.file_uploader("Subir Capacidad", type=["xlsx"], key="u1", label_visibility="collapsed")
        if f1:
            df_cap = pd.read_excel(f1)
            guardar_archivo(f1, "capacidad_planta")
            st.success("Cargado")
            st.dataframe(df_cap, use_container_width=True, height=150)
        else:
            st.info("Esperando archivo...")
        st.markdown('</div>', unsafe_allow_html=True)

    # Materiales
    with col2:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 📦 Maestro de materiales")
        f2 = st.file_uploader("Subir Materiales", type=["xlsx"], key="u2", label_visibility="collapsed")
        if f2:
            df_mat = pd.read_excel(f2)
            guardar_archivo(f2, "maestro_materiales")
            st.success("Cargado")
            st.dataframe(df_mat, use_container_width=True, height=400)
        else:
            st.info("Esperando archivo...")
        st.markdown('</div>', unsafe_allow_html=True)

    col3, col4 = st.columns(2)

    # Clientes
    with col3:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 👥 Maestro de clientes")
        f3 = st.file_uploader("Subir Clientes", type=["xlsx"], key="u3", label_visibility="collapsed")
        if f3:
            df_cli = pd.read_excel(f3)
            guardar_archivo(f3, "maestro_clientes")
            st.success("Cargado")
            st.dataframe(df_cli, use_container_width=True, height=400)
        else:
            st.info("Esperando archivo...")
        st.markdown('</div>', unsafe_allow_html=True)

    # Demanda
    with col4:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 📈 Demanda")
        f4 = st.file_uploader("Subir Demanda", type=["xlsx"], key="u4", label_visibility="collapsed")
        if f4:
            df_dem = pd.read_excel(f4)
            guardar_archivo(f4, "demanda")
            st.success("Cargado")
            st.dataframe(df_dem, use_container_width=True, height=400)
        else:
            st.info("Esperando archivo...")
        st.markdown('</div>', unsafe_allow_html=True)

# --- TAB 2 ---
with tab2:
    # ✅ Fix del error de evaluación booleana de DataFrames
    if any(x is None for x in [df_cap, df_mat, df_cli, df_dem]):
        st.warning("⚠️ Carga los 4 archivos primero")
        st.stop()

    # Limpieza de columnas
    for d in [df_cap, df_mat, df_cli, df_dem]:
        d.columns = d.columns.str.strip()

    centros = list(df_cap["Centro"].astype(str).unique())
    df_dem["Semana_Label"] = pd.to_datetime(df_dem["Fecha de necesidad"]).dt.strftime("%Y-W%U")
    semanas = sorted(df_dem["Semana_Label"].unique())

    st.subheader("⚙️ Configuración de empates (y fuerza por semana: 100% = DG, 0% = MCH)")
    ajustes = {sem: st.slider(f"Semana {sem}", 0, 100, 50) for sem in semanas}

    st.markdown("---")

    if st.button("🚀 Ejecutar cálculo de propuesta", use_container_width=True):
        with st.spinner("Calculando..."):
            df_res = procesar_logica_estable(df_dem, df_mat, df_cli, df_cap, ajustes)

        # ===========================================================
        # 🔧 REASIGNACIÓN MANUAL DE CENTRO POR SEMANA (forzada)
        #    100% -> DG (0833), 0% -> MCH (0184)
        # ===========================================================
        if len(centros) >= 2:
            DG = next((c for c in centros if c.endswith("833")), centros[0])
            MCH = next((c for c in centros if c.endswith("184") and c != DG), (centros[1] if len(centros) > 1 else centros[0]))
            for semana, pct in ajustes.items():
                if pct == 100:
                    df_res.loc[df_res["Semana"] == semana, "Centro"] = DG
                elif pct == 0:
                    df_res.loc[df_res["Semana"] == semana, "Centro"] = MCH

            # 🧮 Recalcular Horas coherentes con el centro forzado
            #    (merge con df_mat para obtener tiempos por centro)
            tiempos = df_mat[["Material", "Unidad", "Tiempo fabricación unidad DG", "Tiempo fabricación unidad MCH"]]
            tmp = df_res.merge(tiempos, on=["Material", "Unidad"], how="left")
            df_res["Horas"] = np.where(
                tmp["Centro"].astype(str) == str(DG),
                df_res["Cantidad a fabricar"] * tmp["Tiempo fabricación unidad DG"],
                df_res["Cantidad a fabricar"] * tmp["Tiempo fabricación unidad MCH"]
            )

        st.success("Cálculo completado")

        # Mostrar tabla (ocultamos Horas en la vista)
        st.dataframe(df_res.drop(columns=["Horas"], errors="ignore"), use_container_width=True)

        # Exportación (sin Semana/Horas)
        out = os.path.join(UPLOAD_DIR, "Propuesta_Final.xlsx")
        df_res.drop(columns=["Semana", "Horas"], errors="ignore").to_excel(out, index=False)

        with open(out, "rb") as f:
            st.download_button("📥 Descargar Excel", f,
                file_name=f"Propuesta_Fabricacion_{datetime.now().strftime('%Y%m%d')}.xlsx")

# Footer
st.markdown("---")
st.markdown("""
<div class="footer">
✨ <strong>Sistema de Cálculo de Fabricación</strong> - Versión 3.2 (Interfaz Unificada)
</div>
""", unsafe_allow_html=True)
