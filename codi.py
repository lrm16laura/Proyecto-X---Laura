# ============================================================
# SISTEMA DE CÁLCULO DE FABRICACIÓN — MODO C + AJUSTE + RE-MODO C
# Estilo visual unificado + Gráficas (Opción B)
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

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
# ESTILOS CSS (idéntico a tu referencia visual)
# ------------------------------------------------------------
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
    .small-note { color:#7f8c8d; font-size:0.85rem; }
    </style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# CONSTANTES Y UTILIDADES
# ------------------------------------------------------------
UPLOAD_DIR = "archivos_cargados"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def guardar_archivo(archivo, nombre_seccion):
    """Guarda el archivo subido con sello de tiempo en una carpeta local."""
    if archivo is not None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"{nombre_seccion}_{timestamp}.xlsx"
        ruta_archivo = os.path.join(UPLOAD_DIR, nombre_archivo)
        with open(ruta_archivo, "wb") as f:
            f.write(archivo.getbuffer())
        return ruta_archivo
    return None

def to_float_safe(v, default=0.0):
    """Convierte valores a float, aceptando coma decimal y vacíos."""
    if pd.isna(v): return float(default)
    if isinstance(v, str):
        v = v.replace(",", ".").strip()
        if v == "": return float(default)
    try:
        return float(v)
    except Exception:
        return float(default)

def detectar_centros(df_cap):
    """Detecta DG/MCH por heurística (sufijos típicos) o por orden."""
    centros = [str(c) for c in df_cap["Centro"].astype(str).unique()]
    DG = next((c for c in centros if c.endswith("833")), centros[0])
    MCH = next((c for c in centros if c.endswith("184") and c != DG),
               centros[1] if len(centros) > 1 else centros[0])
    return DG, MCH, centros

# ------------------------------------------------------------
# REPARTO PROPORCIONAL POR SEMANA (POR HORAS)
# ------------------------------------------------------------
def repartir_porcentaje(df_semana, pct_dg, dg_code, mch_code):
    """
    Reparte proporcionalmente HORAS: pct_dg% a DG, resto a MCH.
    Mantiene las líneas, reasignando 'Centro' por prioridad de horas.
    """
    if df_semana.empty:
        return df_semana
    if pct_dg <= 0:
        df_semana["Centro"] = mch_code
        return df_semana
    if pct_dg >= 100:
        df_semana["Centro"] = dg_code
        return df_semana

    df_semana = df_semana.sort_values("Horas", ascending=False).copy()
    total_h = df_semana["Horas"].sum()
    objetivo = total_h * (pct_dg / 100.0)

    acumulado = 0.0
    centros = []
    for _, r in df_semana.iterrows():
        if acumulado < objetivo:
            centros.append(dg_code)
            acumulado += float(r["Horas"])
        else:
            centros.append(mch_code)
    df_semana["Centro"] = centros
    return df_semana

# ------------------------------------------------------------
# MODO C — PLANIFICACIÓN CON CAPACIDAD DIARIA, LOTE Y DESPLAZAMIENTO +1 DÍA
# ------------------------------------------------------------
def modo_C(df_agrupado, df_cap, df_mat):
    """
    Aplica la planificación Modo C:
      - Capacidad diaria por centro (desde Excel).
      - Divide por lotes (mínimo/máximo).
      - Si no cabe, mueve únicamente al día siguiente, mismo centro.
      - Respeta fecha mínima (no antes de la fecha de necesidad).
      - Devuelve líneas con fecha 'dd.MM.yyyy'.
    Mantiene Lote_min y Lote_max en la salida.
    """
    DG, MCH, centros = detectar_centros(df_cap)

    # Merge tiempos de fabricación
    tiempos = df_mat[[
        "Material", "Unidad",
        "Tiempo fabricación unidad DG",
        "Tiempo fabricación unidad MCH",
        "Tamaño lote mínimo", "Tamaño lote máximo"
    ]].drop_duplicates()

    df = df_agrupado.merge(
        tiempos,
        on=["Material", "Unidad"],
        how="left",
        suffixes=("","_mat")
    )

    # Capacidad base por centro (hora/capacidad)
    horas_col = next((c for c in df_cap.columns
                      if "hora" in c.lower() or "capacidad" in c.lower()), None)
    base = {}
    for centro in centros:
        vals = pd.to_numeric(
            df_cap.loc[df_cap["Centro"].astype(str) == centro, horas_col],
            errors="coerce"
        )
        cap = vals.max()
        base[str(centro)] = float(0 if pd.isna(cap) else cap)

    capacidad_restante = {}
    def get_cap(centro, fecha):
        clave = (str(centro), fecha)
        if clave not in capacidad_restante:
            capacidad_restante[clave] = base.get(str(centro), 0.0)
        return capacidad_restante[clave]
    def consume(centro, fecha, horas):
        capacidad_restante[(str(centro), fecha)] = get_cap(centro, fecha) - float(horas)

    def tiempo_necesario(centro, qty, r):
        tu = to_float_safe(
            r["Tiempo fabricación unidad DG"] if centro == DG else r["Tiempo fabricación unidad MCH"], 0
        )
        return qty * tu

    def cantidad_por_capacidad(centro, cap_horas, r):
        tu = to_float_safe(
            r["Tiempo fabricación unidad DG"] if centro == DG else r["Tiempo fabricación unidad MCH"], 0
        )
        return (cap_horas / tu) if tu > 0 else 0

    out = []
    contador = 1
    MAX_DIAS = 365

    # Normaliza fechas de entrada (pueden venir como str dd.MM.yyyy o datetime)
    def parse_fecha(x):
        if isinstance(x, (pd.Timestamp, datetime)):
            return pd.to_datetime(x).normalize()
        x = str(x)
        # intenta dd.MM.yyyy
        try:
            return pd.to_datetime(x, format="%d.%m.%Y").normalize()
        except Exception:
            return pd.to_datetime(x).normalize()

    # Asegurar columnas de lote si no vienen en df_agrupado
    if "Lote_min" not in df.columns:
        df["Lote_min"] = df.get("Tamaño lote mínimo", np.nan)
    if "Lote_max" not in df.columns:
        df["Lote_max"] = df.get("Tamaño lote máximo", np.nan)

    for _, r in df.iterrows():
        centro = str(r["Centro"])
        fecha = parse_fecha(r["Fecha"])
        semana = r["Semana"] if "Semana" in r else fecha.strftime("%Y-W%U")

        total = max(
            to_float_safe(r["Cantidad"], 0),
            to_float_safe(r.get("Lote_min", r.get("Tamaño lote mínimo", 0)), 0)
        )
        lote_max = max(
            1.0,
            to_float_safe(r.get("Lote_max", r.get("Tamaño lote máximo", 1)), 1)
        )
        lote_min = to_float_safe(r.get("Lote_min", r.get("Tamaño lote mínimo", 0)), 0)

        # Troceo en lotes por Lote_max
        lotes = []
        resto = total
        while resto > 0:
            q = min(resto, lote_max)
            lotes.append(round(q, 2))
            resto = round(resto - q, 6)

        for ql in lotes:
            pendiente = ql
            dias = 0

            # Si la capacidad base del centro es 0, planifica completo en fecha mínima
            if base.get(str(centro), 0) <= 0:
                out.append({
                    "Nº de propuesta": contador,
                    "Material": r["Material"],
                    "Centro": centro,
                    "Clase de orden": "NORM",
                    "Cantidad a fabricar": round(pendiente, 2),
                    "Unidad": r["Unidad"],
                    "Fecha": fecha.strftime("%d.%m.%Y"),
                    "Semana": semana,
                    "Lote_min": lote_min,
                    "Lote_max": lote_max
                })
                contador += 1
                continue

            while pendiente > 0:
                cap_dia = get_cap(centro, fecha)
                horas_nec = tiempo_necesario(centro, pendiente, r)

                if cap_dia >= horas_nec:
                    # Cabe entero hoy
                    consume(centro, fecha, horas_nec)
                    out.append({
                        "Nº de propuesta": contador,
                        "Material": r["Material"],
                        "Centro": centro,
                        "Clase de orden": "NORM",
                        "Cantidad a fabricar": round(pendiente, 2),
                        "Unidad": r["Unidad"],
                        "Fecha": fecha.strftime("%d.%m.%Y"),
                        "Semana": semana,
                        "Lote_min": lote_min,
                        "Lote_max": lote_max
                    })
                    contador += 1
                    pendiente = 0
                    break

                # Producir parte según capacidad
                q_posible = cantidad_por_capacidad(centro, cap_dia, r)
                if q_posible > 0:
                    h_prod = tiempo_necesario(centro, q_posible, r)
                    consume(centro, fecha, h_prod)
                    out.append({
                        "Nº de propuesta": contador,
                        "Material": r["Material"],
                        "Centro": centro,
                        "Clase de orden": "NORM",
                        "Cantidad a fabricar": round(q_posible, 2),
                        "Unidad": r["Unidad"],
                        "Fecha": fecha.strftime("%d.%m.%Y"),
                        "Semana": semana,
                        "Lote_min": lote_min,
                        "Lote_max": lote_max
                    })
                    contador += 1
                    pendiente = round(pendiente - q_posible, 6)

                if pendiente <= 0:
                    break

                if dias >= MAX_DIAS:
                    # Fuerza cierre donde está
                    out.append({
                        "Nº de propuesta": contador,
                        "Material": r["Material"],
                        "Centro": centro,
                        "Clase de orden": "NORM",
                        "Cantidad a fabricar": round(pendiente, 2),
                        "Unidad": r["Unidad"],
                        "Fecha": fecha.strftime("%d.%m.%Y"),
                        "Semana": semana,
                        "Lote_min": lote_min,
                        "Lote_max": lote_max
                    })
                    contador += 1
                    pendiente = 0
                    break

                # Mover SOLO al día siguiente, MISMO centro
                fecha = (fecha + timedelta(days=1)).normalize()
                semana = fecha.strftime("%Y-W%U")
                dias += 1

    return pd.DataFrame(out)

# ------------------------------------------------------------
# EJECUCIÓN END-TO-END: Modo C → Ajuste → Re-Modo C
# ------------------------------------------------------------
def ejecutar_calculo(df_cap, df_mat, df_cli, df_dem, ajustes):
    DG, MCH, _ = detectar_centros(df_cap)

    # Normalización fechas y semana
    df_dem = df_dem.copy()
    df_dem["Fecha_DT"] = pd.to_datetime(df_dem["Fecha de necesidad"])
    df_dem["Semana_Label"] = df_dem["Fecha_DT"].dt.strftime("%Y-W%U")

    # Merge con maestros
    df = df_dem.merge(df_mat, on=["Material", "Unidad"], how="left")
    df = df.merge(df_cli, on="Cliente", how="left")

    # Decisión por coste real (DG vs MCH), con exclusividades
    # Admite nombres frecuentes de columnas:
    col_excl_dg = next((c for c in df.columns if str(c).strip().lower() in ["exclusico dg","exclusivo dg"]), None)
    col_excl_mch = next((c for c in df.columns if str(c).strip().lower() in ["exclusivo mch","exclusivo mch."]), None)

    COL_COST_DG = next((c for c in df.columns if "coste" in c.lower() and "env" in c.lower() and "dg" in c.lower()), "Coste del envío DG")
    COL_COST_MCH = next((c for c in df.columns if "coste" in c.lower() and "env" in c.lower() and "mch" in c.lower()), "Coste del envío MCH")
    COL_CU_DG = next((c for c in df.columns if "coste unit" in c.lower() and "dg" in c.lower()), "Coste unitario DG")
    COL_CU_MCH = next((c for c in df.columns if "coste unit" in c.lower() and "mch" in c.lower()), "Coste unitario MCH")

    def decidir_centro(r):
        # Exclusividades
        if col_excl_dg and str(r.get(col_excl_dg, "")).strip().upper() == "X":
            return DG
        if col_excl_mch and str(r.get(col_excl_mch, "")).strip().upper() == "X":
            return MCH

        c1 = to_float_safe(r.get(COL_COST_DG, 0)) + to_float_safe(r.get("Cantidad", 0)) * to_float_safe(r.get(COL_CU_DG, 0))
        c2 = to_float_safe(r.get(COL_COST_MCH, 0)) + to_float_safe(r.get("Cantidad", 0)) * to_float_safe(r.get(COL_CU_MCH, 0))
        return DG if c1 < c2 else MCH

    df["Centro_Base"] = df.apply(decidir_centro, axis=1)

    # Agrupar demanda por material/unidad/centro/fecha
    g = df.groupby(
        ["Material", "Unidad", "Centro_Base", "Fecha de necesidad", "Semana_Label"], dropna=False
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
    g["Lote_min"] = g["Tamaño lote mínimo"]
    g["Lote_max"] = g["Tamaño lote máximo"]

    # ----------------------
    # PRIMER MODO C
    # ----------------------
    df_c = modo_C(
        df_agrupado=g[["Material","Unidad","Centro","Cantidad","Fecha","Semana","Lote_min","Lote_max"]],
        df_cap=df_cap, df_mat=df_mat
    )

    # Horas para reparto (según centro de cada línea actual)
    tiempos = df_mat[["Material","Unidad","Tiempo fabricación unidad DG","Tiempo fabricación unidad MCH"]].drop_duplicates()
    df_c = df_c.merge(tiempos, on=["Material","Unidad"], how="left")
    DG_code, MCH_code, centros = detectar_centros(df_cap)
    df_c["Horas"] = np.where(
        df_c["Centro"].astype(str) == str(DG_code),
        df_c["Cantidad a fabricar"] * df_c["Tiempo fabricación unidad DG"],
        df_c["Cantidad a fabricar"] * df_c["Tiempo fabricación unidad MCH"]
    )

    # Mantener Lote_min/Max en el flujo para la replanificación posterior
    # (ya están incluidos en df_c desde modo_C)

    # ----------------------
    # REPARTO PROPORCIONAL POR SEMANA
    # ----------------------
    df_repartido = []
    semanas_unicas = sorted(df_c["Semana"].dropna().unique().tolist())
    for sem in semanas_unicas:
        df_sem = df_c[df_c["Semana"] == sem].copy()
        pct = ajustes.get(sem, 50)
        if df_sem.empty:
            continue
        df_sem = repartir_porcentaje(df_sem, pct, DG_code, MCH_code)
        df_repartido.append(df_sem)
    df_adj = pd.concat(df_repartido, ignore_index=True) if df_repartido else df_c.copy()

    # ----------------------
    # RE-APLICAR MODO C COMPLETO DESDE CERO
    # ----------------------
    # Reagrupar las líneas ajustadas por centro, pero respetando fecha mínima
    df_adj_pre = df_adj.rename(columns={
        "Cantidad a fabricar": "Cantidad",
        "Fecha": "Fecha",
    })[["Material","Unidad","Centro","Cantidad","Fecha","Semana","Lote_min","Lote_max"]]

    df_final = modo_C(df_adj_pre, df_cap, df_mat)

    # Calcular horas finales (para métricas y gráficos)
    df_final = df_final.merge(tiempos, on=["Material","Unidad"], how="left")
    df_final["Horas"] = np.where(
        df_final["Centro"].astype(str) == str(DG_code),
        df_final["Cantidad a fabricar"] * df_final["Tiempo fabricación unidad DG"],
        df_final["Cantidad a fabricar"] * df_final["Tiempo fabricación unidad MCH"]
    )

    return df_final, centros, DG_code, MCH_code

# ------------------------------------------------------------
# INTERFAZ
# ------------------------------------------------------------
st.markdown("<h1>📊 Sistema de Cálculo de Fabricación</h1>", unsafe_allow_html=True)
st.markdown("Carga los 4 archivos Excel necesarios, ajusta los porcentajes por semana y ejecuta el cálculo completo (Modo C → Reparto → Re‑Modo C).")
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
        f1 = st.file_uploader("Subir Capacidad", type=["xlsx"], key="u1", label_visibility="collapsed")
        if f1:
            try:
                df_cap = pd.read_excel(f1)
                guardar_archivo(f1, "capacidad_planta")
                st.success("✅ Cargado")
                st.dataframe(df_cap, use_container_width=True, height=150)
                st.caption("La app detectará automáticamente la columna de horas/capacidad.")
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
                st.success("✅ Cargado")
                st.dataframe(df_dem, use_container_width=True, height=400)
            except Exception as e:
                st.error(f"Error al leer Demanda: {e}")
        else:
            st.info("Esperando archivo…")
        st.markdown('</div>', unsafe_allow_html=True)

# =========================
# TAB 2 — EJECUCIÓN
# =========================
with tab2:
    if any(x is None for x in [df_cap, df_mat, df_cli, df_dem]):
        st.warning("⚠️ Por favor, carga los 4 archivos en la pestaña anterior para habilitar los ajustes.")
        st.stop()

    # Limpieza de columnas
    for d in [df_cap, df_mat, df_cli, df_dem]:
        d.columns = d.columns.str.strip()

    # Semanas disponibles
    df_dem["Semana_Label"] = pd.to_datetime(df_dem["Fecha de necesidad"]).dt.strftime("%Y-W%U")
    lista_semanas = sorted(df_dem["Semana_Label"].dropna().unique())

    # Sliders en grid (4 columnas)
    st.subheader("⚙️ Configuración de Porcentajes por Semana (0% = MCH · 100% = DG)")
    DG_code, MCH_code, centros_detectados = detectar_centros(df_cap)
    st.info(f"El sistema asigna por coste real. En caso de empate técnico, usa estos porcentajes para repartir horas entre **{DG_code}** y **{MCH_code}**.")

    ajustes = {}
    cols_sliders = st.columns(4)
    for i, sem in enumerate(lista_semanas):
        with cols_sliders[i % 4]:
            ajustes[sem] = st.slider(f"Sem {sem}", 0, 100, 50)

    st.markdown("---")

    if st.button("🚀 EJECUTAR CÁLCULO DE PROPUESTA", use_container_width=True):
        with st.spinner("Calculando Modo C → Reparto → Re‑Modo C…"):
            df_res, centros, DG, MCH = ejecutar_calculo(df_cap, df_mat, df_cli, df_dem, ajustes)

        st.success("✅ Cálculo completado con éxito.")

        # =========================
        # MÉTRICAS
        # =========================
        total_props = len(df_res)
        horas_por_centro = df_res.groupby("Centro")["Horas"].sum().to_dict()

        # Capacidad base por centro (para saturación)
        horas_col = next((c for c in df_cap.columns
                          if "hora" in c.lower() or "capacidad" in c.lower()), None)
        cap_base = {}
        for c in centros:
            vals = pd.to_numeric(df_cap.loc[df_cap["Centro"].astype(str) == c, horas_col], errors="coerce")
            cap_base[c] = float(0 if vals.dropna().empty else vals.max())

        # Días planificados por centro (para capacidad total disponible)
        df_res["_FechaDT"] = pd.to_datetime(df_res["Fecha"], format="%d.%m.%Y", errors="coerce")
        dias_por_centro = df_res.groupby("Centro")["_FechaDT"].nunique().to_dict()
        cap_total_disp = {c: cap_base.get(c, 0) * dias_por_centro.get(c, 0) for c in centros}
        sat_pct = {
            c: (horas_por_centro.get(c, 0) / cap_total_disp.get(c, 1) * 100) if cap_total_disp.get(c, 0) > 0 else 0
            for c in centros
        }

        m = st.columns(3)
        m[0].metric("Total Propuestas", f"{total_props:,}".replace(",", "."))
        if len(centros) >= 1:
            c0 = centros[0]
            m[1].metric(f"Horas Totales {c0}", f"{horas_por_centro.get(c0, 0):,.1f}h".replace(",", "."),
                        help=f"Saturación: {sat_pct.get(c0, 0):.1f}%")
        if len(centros) >= 2:
            c1 = centros[1]
            m[2].metric(f"Horas Totales {c1}", f"{horas_por_centro.get(c1, 0):,.1f}h".replace(",", "."),
                        help=f"Saturación: {sat_pct.get(c1, 0):.1f}%")

        # =========================
        # GRÁFICAS — OPCIÓN B
        # =========================
        st.subheader("📊 Gráficas de Carga y Capacidad")

        # ---- 1) Carga por día y centro (barras apiladas por centro) ----
        st.markdown("**Carga diaria por centro (Horas)**")
        df_day = df_res.copy()
        df_day["_FechaDT"] = pd.to_datetime(df_day["Fecha"], format="%d.%m.%Y", errors="coerce")
        carga_por_dia = df_day.groupby(["_FechaDT","Centro"])["Horas"].sum().unstack().fillna(0).sort_index()
        st.bar_chart(carga_por_dia, use_container_width=True)

        # ---- 2) Carga por material (Top N) ----
        st.markdown("**Carga total por material (Top 20)**")
        topN = 20
        carga_material = df_res.groupby("Material")["Horas"].sum().sort_values(ascending=False).head(topN)
        st.bar_chart(carga_material.to_frame(name="Horas"), use_container_width=True)

        # ---- 3) Carga por centro (tarta) ----
        st.markdown("**Distribución por centro (%)**")
        pie_data = df_res.groupby("Centro")["Horas"].sum()
        fig_pie, ax_pie = plt.subplots(figsize=(4.5, 4.5))
        if pie_data.sum() > 0:
            ax_pie.pie(pie_data.values, labels=pie_data.index, autopct="%1.1f%%", startangle=90)
            ax_pie.axis('equal')
        else:
            ax_pie.text(0.5, 0.5, "Sin datos", ha="center", va="center")
            ax_pie.axis('off')
        st.pyplot(fig_pie, use_container_width=False)

        # ---- 4) Capacidad usada vs disponible (líneas) ----
        st.markdown("**Capacidad usada vs. disponible (por centro)**")
        cols_cap = st.columns(max(1, len(centros)))
        for idx, c in enumerate(centros):
            with cols_cap[idx]:
                df_centro = df_day[df_day["Centro"] == c].copy()
                serie_usado = df_centro.groupby("_FechaDT")["Horas"].sum().rename("Usado").sort_index()
                serie_cap = pd.Series(
                    cap_base.get(c, 0.0), index=serie_usado.index, name="Capacidad"
                )
                df_uc = pd.concat([serie_usado, serie_cap], axis=1).fillna(0.0)

                st.markdown(f"**{c}** — Capacidad base: **{cap_base.get(c, 0):,.1f} h/día**".replace(",", "."))
                st.line_chart(df_uc, use_container_width=True)
                st.caption(f"Saturación global: {sat_pct.get(c, 0):.1f}%")

        st.markdown("---")

        # =========================
        # TABLAS
        # =========================
        st.subheader("📋 Detalle de la Propuesta")
        st.caption("Fechas en formato dd.MM.yyyy. Lote mínimos/máximos se arrastran en todo el flujo.")
        cols_to_show = ["Nº de propuesta","Material","Centro","Clase de orden",
                        "Cantidad a fabricar","Unidad","Fecha","Semana",
                        "Lote_min","Lote_max"]
        cols_presentes = [c for c in cols_to_show if c in df_res.columns]
        st.dataframe(df_res[cols_presentes], use_container_width=True, height=400)

        # =========================
        # EXPORTACIÓN
        # =========================
        output_path = os.path.join(UPLOAD_DIR, f"Propuesta_Final_{datetime.now().strftime('%Y%m%d')}.xlsx")
        # Exporta sin columnas técnicas
        export_cols = cols_presentes  # ya son limpias
        df_res[export_cols].to_excel(output_path, index=False)

        with open(output_path, "rb") as f:
            st.download_button(
                "📥 Descargar Propuesta en Excel",
                data=f,
                file_name=f"Propuesta_Fabricacion_{datetime.now().strftime('%Y%m%d')}.xlsx"
            )

# Footer
st.markdown("---")
st.markdown("""
<div class="footer">
    <p>✨ <strong>Sistema de Cálculo de Fabricación</strong> — Interfaz Unificada</p>
    <p>Modo C + Reparto Proporcional + Re‑Modo C | Fechas dd.MM.yyyy</p>
</div>
""", unsafe_allow_html=True)
