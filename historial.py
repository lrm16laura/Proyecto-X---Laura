# ============================================================
# SISTEMA DE CÁLCULO DE FABRICACIÓN — Versión con HISTORIAL localStorage
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
from pathlib import Path

# --- NUEVO: LocalStorage del navegador ---
from streamlit_local_storage import LocalStorage
localS = LocalStorage()
HIST_KEY = "historial_min"

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
# CARPETAS LOCALES (solo para archivos Excel)
# ------------------------------------------------------------
UPLOAD_DIR = "archivos_cargados"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ============================================================
# HISTORIAL EN LOCALSTORAGE
# ============================================================

def log_mini(action: str):
    """Guarda un evento en el localStorage del navegador."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = localS.getItem(HIST_KEY)
    if data is None:
        data = []
    data.append({"ts": now, "action": action})
    localS.setItem(HIST_KEY, data)

def last_status():
    """Devuelve últimos timestamps de cálculo inicial y replanificación."""
    data = localS.getItem(HIST_KEY)
    if not data:
        return None, None

    ult_calc = None
    ult_repl = None

    for row in data:
        if row["action"] == "calculo_inicial":
            ult_calc = row["ts"]
        if row["action"] == "replanificacion":
            ult_repl = row["ts"]

    return ult_calc, ult_repl

def list_generated_files():
    """Lista archivos Excel generados por la app."""
    files = set(st.session_state.get("archivos_generados", []))
    if os.path.isdir(UPLOAD_DIR):
        for fn in os.listdir(UPLOAD_DIR):
            if fn.endswith(".xlsx") and (fn.startswith("Propuesta Inicial") or fn.startswith("Propuesta Replan")):
                files.add(os.path.join(UPLOAD_DIR, fn))
    files = [p for p in files if os.path.exists(p)]
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return files
  # ------------------------------------------------------------
# ESTILOS CSS
# ------------------------------------------------------------
st.markdown("""
<style>
.main { padding-top: 2rem; }
h2 { color: #2c3e50; border-bottom: 3px solid #1f77b4; padding-bottom: 0.5rem; }
.section-container {
    background-color: #f8f9fa;
    padding: 1.5rem;
    border-radius: 10px;
    border-left: 5px solid #1f77b4;
    margin-bottom: 1.5rem;
}
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
# UTILIDADES
# ------------------------------------------------------------
def guardar_archivo(archivo, nombre):
    if archivo is not None:
        t = datetime.now().strftime("%Y%m%d_%H%M%S")
        p = os.path.join(UPLOAD_DIR, f"{nombre} {t}.xlsx")
        with open(p, "wb") as f:
            f.write(archivo.getbuffer())
        return p
    return None

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
    iso = ts.isocalendar()
    return f"{int(iso.year)}-W{int(iso.week):02d}"
# ------------------------------------------------------------
# LECTURA Y MERGE DE DATOS
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

def detectar_centros_desde_capacidades(capacidades):
    keys = list(capacidades.keys())
    DG = next((k for k in keys if k.endswith("833")), keys[0])
    MCH = next((k for k in keys if k.endswith("184")), keys[-1])
    return DG, MCH, keys
