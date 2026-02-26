# ============================================================
# SISTEMA DE CÁLCULO DE FABRICACIÓN — MODO C + AJUSTE + RE-MODO C
# Estilo visual unificado + Gráficas (Opción B) + Lectura exacta "Capacidad horas"
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
import altair as alt  # Usamos Altair para el pie chart (compatible con Streamlit Cloud)

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
# ESTILOS CSS (idéntico al estilo de referencia)
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
    """Guarda el archivo subido con sello de tiempo."""
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

def norm_code(code):
    """
    Normaliza el código de centro:
    - Convierte a str
    - Extrae dígitos
    - Rellena a 4 dígitos si aplica (ej. 833 -> 0833)
    """
    s = str(code).strip()
    # Elimina decimales tipo '833.0'
    if s.endswith(".0"): s = s[:-2]
    # Solo dígitos
    digits = "".join(ch for ch in s if ch.isdigit())
    if digits == "":
        return s
    if len(digits) < 4:
        digits = digits.zfill(4)
    return digits

def leer_capacidades(df_cap):
    """
    Lee exactamente la columna 'Capacidad horas' por centro.
    Estructura esperada (según tu Excel):
      - 'Planta' (no se usa)
      - 'Centro'
      - 'Capacidad horas'
    """
    if "Centro" not in df_cap.columns:
        st.error("❌ No se encuentra la columna 'Centro' en el Excel de capacidad.")
        st.stop()

    # Buscar la columna exacta 'Capacidad horas' (permitimos pequeñas variantes)
    col_nor = {c: c.strip().lower() for c in df_cap.columns}
    cap_col = None
    for col, low in col_nor.items():
        if low == "capacidad horas" or (("capacidad" in low) and ("hora" in low)):
            cap_col = col
            break

    if cap_col is None:
        st.error("❌ No se encuentra la columna 'Capacidad horas' en el Excel de capacidad.")
        st.stop()

    capacidades = {}
    for _, r in df_cap.iterrows():
        c = norm_code(r["Centro"])
        capacidades[c] = to_float_safe(r[cap_col], 0.0)

    if not capacidades:
        st.error("❌ No se han podido leer capacidades del Excel.")
        st.stop()

    return capacidades

def detectar_centros_desde_capacidades(capacidades):
    """
    Identifica DG y MCH usando sufijos habituales.
    DG = termina en '833'
    MCH = termina en '184'
    """
    keys = list(capacidades.keys())
    DG = next((k for k in keys if k.endswith("833")), keys[0])
    MCH = next((k for k in keys if k.endswith("184") and k != DG),
               keys[1] if len(keys) > 1 else keys[0])
    return DG, MCH, keys

# ------------------------------------------------------------
# REPARTO PROPORCIONAL POR SEMANA (POR HORAS)
# ------------------------------------------------------------
def repartir_porcentaje(df_semana, pct_dg, dg_code, mch_code):
    """
    Reparte proporcionalmente HORAS: pct_dg% a DG, resto a MCH.
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
# MODO C — PLANIFICACIÓN (capacidad diaria, lotes, mover +1 día, mismo centro)
# ------------------------------------------------------------
def modo_C(df_agrupado, df_mat, capacidades, DG_code, MCH_code):
    """
    Aplica la planificación Modo C:
      - Capacidad diaria por centro (desde Excel 'Capacidad horas').
      - Divide por lotes (mínimo/máximo).
      - Si no cabe, mueve solo al día siguiente, mismo centro.
      - Respeta fecha mínima.
      - Devuelve 'Fecha' en formato dd.MM.yyyy.
    Mantiene Lote_min y Lote_max.
    """

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

    capacidad_restante = {}
    def get_cap(centro, fecha):
        clave = (str(centro), fecha)
        if clave not in capacidad_restante:
            capacidad_restante[clave] = float(capacidades.get(str(centro), 0.0))
        return capacidad_restante[clave]

    def consume(centro, fecha, horas):
        capacidad_restante[(str(centro), fecha)] = get_cap(centro, fecha) - float(horas)

    def tiempo_necesario(centro, qty, r):
        tu = to_float_safe(
            r["Tiempo fabricación unidad DG"] if str(centro) == str(DG_code) else r["Tiempo fabricación unidad MCH"], 0
        )
        return qty * tu

    def cantidad_por_capacidad(centro, cap_horas, r):
        tu = to_float_safe(
            r["Tiempo fabricación unidad DG"] if str(centro) == str(DG_code) else r["Tiempo fabricación unidad MCH"], 0
        )
        return (cap_horas / tu) if tu > 0 else 0

    def parse_fecha(x):
        if isinstance(x, (pd.Timestamp, datetime)):
            return pd.to_datetime(x).normalize()
        x = str(x)
        try:
            return pd.to_datetime(x, format="%d.%m.%Y").normalize()
        except Exception:
            return pd.to_datetime(x).normalize()

    out = []
    contador = 1
    MAX_DIAS = 365

    # Asegurar columnas lote
    if "Lote_min" not in df.columns:
        df["Lote_min"] = df.get("Tamaño lote mínimo", np.nan)
    if "Lote_max" not in df.columns:
        df["Lote_max"] = df.get("Tamaño lote máximo", np.nan)

    for _, r in df.iterrows():
        centro = norm_code(r["Centro"])
        fecha = parse_fecha(r["Fecha"])
        semana = r["Semana"] if "Semana" in r and pd.notna(r["Semana"]) else fecha.strftime("%Y-W%U")

        total = max(
            to_float_safe(r["Cantidad"], 0),
            to_float_safe(r.get("Lote_min", r.get("Tamaño lote mínimo", 0)), 0)
        )
        lote_max = max(
            1.0,
            to_float_safe(r.get("Lote_max", r.get("Tamaño lote máximo", 1)), 1)
        )
        lote_min = to_float_safe(r.get("Lote_min", r.get("Tamaño lote mínimo", 0)), 0)

        # Troceo por Lote_max
        lotes = []
        resto = total
        while resto > 0:
            q = min(resto, lote_max)
            lotes.append(round(q, 2))
            resto = round(resto - q, 6)

        for ql in lotes:
            pendiente = ql
            dias = 0

            # Si la capacidad base del centro es 0, programar todo en fecha mínima
            if capacidades.get(str(centro), 0) <= 0:
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

                # Producir lo que permita la capacidad del día
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
                    # Forzar cierre
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
    # 1) Capacidades exactas desde Excel
    capacidades = leer_capacidades(df_cap)
    DG_code, MCH_code, centros = detectar_centros_desde_capacidades(capacidades)

    # 2) Normalización fechas y semana
    df_dem = df_dem.copy()
    df_dem["Fecha_DT"] = pd.to_datetime(df_dem["Fecha de necesidad"])
    df_dem["Semana_Label"] = df_dem["Fecha_DT"].dt.strftime("%Y-W%U")

    # 3) Merge con maestros
    df = df_dem.merge(df_mat, on=["Material", "Unidad"], how="left")
    df = df.merge(df_cli, on="Cliente", how="left")

    # 4) Decisión por coste real (DG vs MCH), con exclusividades
    col_excl_dg = next((c for c in df.columns if str(c).strip().lower() in ["exclusico dg","exclusivo dg"]), None)
    col_excl_mch = next((c for c in df.columns if str(c).strip().lower() in ["exclusivo mch","exclusivo mch."]), None)

    COL_COST_DG = next((c for c in df.columns if "coste" in str(c).lower() and "env" in str(c).lower() and "dg" in str(c).lower()), "Coste del envío DG")
    COL_COST_MCH = next((c for c in df.columns if "coste" in str(c).lower() and "env" in str(c).lower() and "mch" in str(c).lower()), "Coste del envío MCH")
    COL_CU_DG = next((c for c in df.columns if "coste unit" in str(c).lower() and "dg" in str(c).lower()), "Coste unitario DG")
    COL_CU_MCH = next((c for c in df.columns if "coste unit" in str(c).lower() and "mch" in str(c).lower()), "Coste unitario MCH")

    def decidir_centro(r):
        # Exclusividades
        if col_excl_dg and str(r.get(col_excl_dg, "")).strip().upper() == "X":
            return DG_code
        if col_excl_mch and str(r.get(col_excl_mch, "")).strip().upper() == "X":
            return MCH_code

        c1 = to_float_safe(r.get(COL_COST_DG, 0)) + to_float_safe(r.get("Cantidad", 0)) * to_float_safe(r.get(COL_CU_DG, 0))
        c2 = to_float_safe(r.get(COL_COST_MCH, 0)) + to_float_safe(r.get("Cantidad", 0)) * to_float_safe(r.get(COL_CU_MCH, 0))
        return DG_code if c1 < c2 else MCH_code

    df["Centro_Base"] = df.apply(decidir_centro, axis=1)

    # 5) Agrupar demanda
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
    g["Centro"] = g["Centro"].apply(norm_code)
    g["Lote_min"] = g["Tamaño lote mínimo"]
    g["Lote_max"] = g["Tamaño lote máximo"]

    # 6) PRIMER MODO C
    df_c = modo_C(
        df_agrupado=g[["Material","Unidad","Centro","Cantidad","Fecha","Semana","Lote_min","Lote_max"]],
        df_mat=df_mat,
        capacidades=capacidades,
        DG_code=DG_code, MCH_code=MCH_code
    )

    # 7) Horas para reparto
    tiempos = df_mat[["Material","Unidad","Tiempo fabricación unidad DG","Tiempo fabricación unidad MCH"]].drop_duplicates()
    df_c = df_c.merge(tiempos, on=["Material","Unidad"], how="left")
    df_c["Horas"] = np.where(
        df_c["Centro"].astype(str) == str(DG_code),
        df_c["Cantidad a fabricar"] * df_c["Tiempo fabricación unidad DG"],
        df_c["Cantidad a fabricar"] * df_c["Tiempo fabricación unidad MCH"]
    )

    # 8) REPARTO PROPORCIONAL POR SEMANA
    df_repartido = []
    for sem in sorted(df_c["Semana"].dropna().unique().tolist()):
        df_sem = df_c[df_c["Semana"] == sem].copy()
        pct = ajustes.get(sem, 50)
        if df_sem.empty:
            continue
        df_sem = repartir_porcentaje(df_sem, pct, DG_code, MCH_code)
        df_repartido.append(df_sem)
    df_adj = pd.concat(df_repartido, ignore_index=True) if df_repartido else df_c.copy()

    # 9) RE-MODO C COMPLETO
    df_adj_pre = df_adj.rename(columns={"Cantidad a fabricar":"Cantidad"})[
        ["Material","Unidad","Centro","Cantidad","Fecha","Semana","Lote_min","Lote_max"]
    ]
    df_final = modo_C(df_adj_pre, df_mat, capacidades, DG_code, MCH_code)

    # 10) Horas finales (para métricas y gráficos)
    df_final = df_final.merge(tiempos, on=["Material","Unidad"], how="left")
    df_final["Horas"] = np.where(
        df_final["Centro"].astype(str) == str(DG_code),
        df_final["Cantidad a fabricar"] * df_final["Tiempo fabricación unidad DG"],
        df_final["Cantidad a fabricar"] * df_final["Tiempo fabricación unidad MCH"]
    )

    return df_final, capacidades, DG_code, MCH_code

# ------------------------------------------------------------
# INTERFAZ
# ------------------------------------------------------------
st.markdown("<h1>📊 Sistema de Cálculo de Fabricación</h1>", unsafe_allow_html=True)
st.markdown("Carga los 4 archivos Excel necesarios, ajusta los porcentajes por semana y ejecuta Modo C → Reparto → Re‑Modo C.")
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
    ajustes = {}
    cols_sliders = st.columns(4)
    for i, sem in enumerate(lista_semanas):
        with cols_sliders[i % 4]:
            ajustes[sem] = st.slider(f"Sem {sem}", 0, 100, 50)

    st.markdown("---")

    if st.button("🚀 EJECUTAR CÁLCULO DE PROPUESTA", use_container_width=True):
        with st.spinner("Calculando Modo C → Reparto → Re‑Modo C…"):
            df_res, capacidades, DG, MCH = ejecutar_calculo(df_cap, df_mat, df_cli, df_dem, ajustes)

        st.success("✅ Cálculo completado con éxito.")

        # =========================
        # Mostrar capacidades leídas
        # =========================
        st.markdown("**Capacidades leídas del Excel (h/día):**")
        st.write({k: f"{v:.1f}" for k, v in capacidades.items()})

        # =========================
        # MÉTRICAS
        # =========================
        total_props = len(df_res)
        horas_por_centro = df_res.groupby("Centro")["Horas"].sum().to_dict()

        # Capacidad base y días planificados (para saturación)
        df_res["_FechaDT"] = pd.to_datetime(df_res["Fecha"], format="%d.%m.%Y", errors="coerce")
        dias_por_centro = df_res.groupby("Centro")["_FechaDT"].nunique().to_dict()
        cap_total_disp = {c: capacidades.get(c, 0) * dias_por_centro.get(c, 0) for c in capacidades.keys()}
        sat_pct = {
            c: (horas_por_centro.get(c, 0) / cap_total_disp.get(c, 1) * 100) if cap_total_disp.get(c, 0) > 0 else 0
            for c in capacidades.keys()
        }

        m = st.columns(3)
        m[0].metric("Total Propuestas", f"{total_props:,}".replace(",", "."))
        # Mostrar dos primeros centros (típicamente DG/MCH)
        centros_orden = list(capacidades.keys())
        if len(centros_orden) >= 1:
            c0 = centros_orden[0]
            m[1].metric(f"Horas Totales {c0}", f"{horas_por_centro.get(c0, 0):,.1f}h".replace(",", "."),
                        help=f"Saturación: {sat_pct.get(c0, 0):.1f}%")
        if len(centros_orden) >= 2:
            c1 = centros_orden[1]
            m[2].metric(f"Horas Totales {c1}", f"{horas_por_centro.get(c1, 0):,.1f}h".replace(",", "."),
                        help=f"Saturación: {sat_pct.get(c1, 0):.1f}%")

        # =========================
        # GRÁFICAS — OPCIÓN B
        # =========================
        st.subheader("📊 Gráficas de Carga y Capacidad")

        # ---- 1) Carga por día y centro (barras) ----
        st.markdown("**Carga diaria por centro (Horas)**")
        df_day = df_res.copy()
        carga_por_dia = df_day.groupby(["_FechaDT","Centro"])["Horas"].sum().unstack().fillna(0).sort_index()
        st.bar_chart(carga_por_dia, use_container_width=True)

        # ---- 2) Carga por material (Top 20) ----
        st.markdown("**Carga total por material (Top 20)**")
        topN = 20
        carga_material = df_res.groupby("Material")["Horas"].sum().sort_values(ascending=False).head(topN)
        st.bar_chart(carga_material.to_frame(name="Horas"), use_container_width=True)

        # ---- 3) Distribución por centro (%) — Pie con Altair (idéntico visual) ----
        st.markdown("**Distribución por centro (%)**")
        pie_data = df_res.groupby("Centro")["Horas"].sum().reset_index()
        if pie_data["Horas"].sum() > 0:
            pie_data["Porcentaje"] = pie_data["Horas"] / pie_data["Horas"].sum()
            chart = alt.Chart(pie_data).mark_arc().encode(
                theta=alt.Theta(field="Porcentaje", type="quantitative"),
                color=alt.Color("Centro:N"),
                tooltip=["Centro", alt.Tooltip("Horas:Q", format=".1f"), alt.Tooltip("Porcentaje:Q", format=".1%")]
            ).properties(width=350, height=350)
            st.altair_chart(chart, use_container_width=False)
        else:
            st.info("Sin datos para mostrar la distribución.")

        # ---- 4) Capacidad usada vs disponible (por centro) ----
        st.markdown("**Capacidad usada vs. disponible (por centro)**")
        cols_cap = st.columns(max(1, len(capacidades)))
        for idx, c in enumerate(capacidades):
            with cols_cap[idx]:
                df_centro = df_day[df_day["Centro"] == c].copy()
                serie_usado = df_centro.groupby("_FechaDT")["Horas"].sum().rename("Usado").sort_index()
                if not serie_usado.index.empty:
                    serie_cap = pd.Series(capacidades.get(c, 0.0), index=serie_usado.index, name="Capacidad")
                else:
                    # En caso extremo sin fechas, crear índice vacío
                    serie_cap = pd.Series(dtype=float, name="Capacidad")
                df_uc = pd.concat([serie_usado, serie_cap], axis=1).fillna(0.0)

                st.markdown(f"**{c}** — Capacidad base: **{capacidades.get(c, 0):,.1f} h/día**".replace(",", "."))
                st.line_chart(df_uc, use_container_width=True)
                st.caption(f"Saturación global: {sat_pct.get(c, 0):.1f}%")

        st.markdown("---")

        # =========================
        # TABLA Y EXPORTACIÓN
        # =========================
        st.subheader("📋 Detalle de la Propuesta")
        cols_to_show = ["Nº de propuesta","Material","Centro","Clase de orden",
                        "Cantidad a fabricar","Unidad","Fecha","Semana",
                        "Lote_min","Lote_max"]
        cols_presentes = [c for c in cols_to_show if c in df_res.columns]
        st.dataframe(df_res[cols_presentes], use_container_width=True, height=420)

        output_path = os.path.join(UPLOAD_DIR, f"Propuesta_Final_{datetime.now().strftime('%Y%m%d')}.xlsx")
        df_res[cols_presentes].to_excel(output_path, index=False)
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
    <p>Modo C + Reparto Proporcional + Re‑Modo C | Fechas dd.MM.yyyy | Capacidades desde “Capacidad horas”</p>
</div>
""", unsafe_allow_html=True)
