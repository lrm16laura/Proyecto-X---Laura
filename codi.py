import streamlit as st
import pandas as pd
import numpy as np
import os
import math
from datetime import datetime

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
# FUNCIONES AUXILIARES Y LÓGICA (Programa 2)
# ==========================================

def guardar_archivo(archivo, nombre_seccion):
    """Guarda el archivo en la carpeta local (del Programa 1)"""
    if archivo is not None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"{nombre_seccion}_{timestamp}.xlsx"
        ruta_archivo = os.path.join(UPLOAD_DIR, nombre_archivo)
        with open(ruta_archivo, "wb") as f:
            f.write(archivo.getbuffer())
        return ruta_archivo
    return None

def procesar_logica_estable(df_dem, df_mat, df_cli, df_cap, ajustes_semanales):
    """Lógica optimizada del Programa 2 (corregida + capacidad)"""
    # --- Centros disponibles (se mantiene tu lógica) ---
    lista_centros_disponibles = df_cap['Centro'].unique().tolist()
    C1 = str(lista_centros_disponibles[0])
    C2 = str(lista_centros_disponibles[1]) if len(lista_centros_disponibles) > 1 else C1

    # Fallback si no existieran columnas de precio envío en el Excel de clientes
    PRECIO_KM = 0.15

    # --- Preparación de semanas ---
    df_dem['Fecha_DT'] = pd.to_datetime(df_dem['Fecha de necesidad'])
    df_dem['Semana_Label'] = df_dem['Fecha_DT'].dt.strftime('%Y-W%U')

    # --- Merge de datos ---
    df = df_dem.merge(df_mat, on=['Material', 'Unidad'], how='left')
    df = df.merge(df_cli, on='Cliente', how='left')

    # --- Detección robusta de nombres de columnas (distancia y coste/km) ---
    cols_lower = {c.lower(): c for c in df.columns}
    def pick(options):
        for opt in options:
            if opt.lower() in cols_lower:
                return cols_lower[opt.lower()]
        return None

    # C1 asumido = DG, C2 asumido = MCH (coincide con tu lógica ya existente)
    dist_c1_col = pick(["Distancia a DG", "Distáncia a DG", "Distancia DG"])
    dist_c2_col = pick(["Distancia a MCH", "Distáncia a MCH", "Distancia MCH"])
    costkm_c1_col = pick(["Coste del envío DG", "Coste envio DG", "Precio KM DG", "Precio km DG", "Coste KM DG"])
    costkm_c2_col = pick(["Coste del envío MCH", "Coste envio MCH", "Precio KM MCH", "Precio km MCH", "Coste KM MCH"])

    # --- Función de decisión de centro (corrige el cálculo de coste total) ---
    def decidir_centro(r):
        # Soporta las dos grafías: "Exclusico DG" (con error) y "Exclusivo DG"
        ex_dg = str(r.get('Exclusico DG', r.get('Exclusivo DG', ''))).strip().upper()
        ex_mch = str(r.get('Exclusivo MCH', '')).strip().upper()
        if ex_dg == 'X': 
            return C1
        if ex_mch == 'X': 
            return C2

        # Distancias y precio por km por centro, leyendo del Excel de clientes
        dist_c1 = float(r.get(dist_c1_col, 0) or 0) if dist_c1_col else 0.0
        dist_c2 = float(r.get(dist_c2_col, 0) or 0) if dist_c2_col else 0.0
        precio_km_c1 = float(r.get(costkm_c1_col, PRECIO_KM) or PRECIO_KM) if costkm_c1_col or PRECIO_KM else 0.0
        precio_km_c2 = float(r.get(costkm_c2_col, PRECIO_KM) or PRECIO_KM) if costkm_c2_col or PRECIO_KM else 0.0

        # Costes unitarios de fabricación
        cf_dg = float(r.get('Coste fabricacion unidad DG', 0) or 0)
        cf_mch = float(r.get('Coste fabricacion unidad MCH', 0) or 0)
        cantidad = float(r.get('Cantidad', 0) or 0)

        # Coste total por centro
        coste_c1 = dist_c1 * precio_km_c1 + cantidad * cf_dg
        coste_c2 = dist_c2 * precio_km_c2 + cantidad * cf_mch

        if coste_c1 < coste_c2:
            return C1
        elif coste_c2 < coste_c1:
            return C2
        else:
            # Empate técnico -> porcentaje semanal
            rng = np.random.RandomState(r.name)
            valor_azar = rng.rand()
            umbral = ajustes_semanales.get(r['Semana_Label'], 50) / 100
            return C1 if valor_azar < umbral else C2

    df['Centro_Final'] = df.apply(decidir_centro, axis=1)

    # --- Agrupación como en tu código original ---
    df_agrupado = df.groupby(
        ['Material', 'Unidad', 'Centro_Final', 'Fecha de necesidad', 'Semana_Label']
    ).agg({
        'Cantidad': 'sum',
        'Tamaño lote mínimo': 'first',
        'Tamaño lote máximo': 'first',
        'Tiempo fabricación unidad DG': 'first',
        'Tiempo fabricación unidad MCH': 'first'
    }).reset_index()

    # ============
    # CAPACIDADES
    # ============
    # Detectar columnas de capacidad en df_cap
    cap_cols_lower = {c.lower(): c for c in df_cap.columns}
    def pick_cap(options):
        for opt in options:
            if opt.lower() in cap_cols_lower:
                return cap_cols_lower[opt.lower()]
        return None

    horas_col = None
    # Preferir columna con "hora" o "capacidad"
    for c in df_cap.columns:
        if ('hora' in c.lower()) or ('capacidad' in c.lower()):
            horas_col = c
            break

    semana_cap_col = pick_cap(["Semana", "Semana_Label", "semana"])

    # Semanas existentes en demanda
    semanas_demanda = sorted(df['Semana_Label'].unique().tolist())

    # Construcción del mapa de capacidad por (centro, semana)
    cap_por_centro_semana = {}
    if horas_col:
        if semana_cap_col:
            # Capacidad variable por semana según df_cap
            for _, row in df_cap.iterrows():
                centro_k = str(row['Centro'])
                semana_k = str(row[semana_cap_col])
                horas = float(row[horas_col] or 0)
                cap_por_centro_semana[(centro_k, semana_k)] = cap_por_centro_semana.get((centro_k, semana_k), 0.0) + horas
        else:
            # Misma capacidad por centro para todas las semanas detectadas
            base_cap_por_centro = {}
            for _, row in df_cap.iterrows():
                centro_k = str(row['Centro'])
                horas = float(row[horas_col] or 0)
                base_cap_por_centro[centro_k] = base_cap_por_centro.get(centro_k, 0.0) + horas
            for semana in semanas_demanda:
                for centro_k, horas in base_cap_por_centro.items():
                    cap_por_centro_semana[(centro_k, semana)] = horas
    else:
        # Si no hay columna de horas/capacidad, considerar capacidad infinita
        for semana in semanas_demanda:
            for centro_k in [C1, C2]:
                cap_por_centro_semana[(centro_k, semana)] = float('inf')

    # Capacidad restante (mutable)
    cap_restante = {k: float(v) for k, v in cap_por_centro_semana.items()}

    # ============================
    # Generación de órdenes/lotes
    # ============================
    resultado_lotes = []
    cont = 1
    for _, fila in df_agrupado.iterrows():
        cant_total = max(float(fila['Cantidad']), float(fila['Tamaño lote mínimo']))
        tam_lote_max = float(fila['Tamaño lote máximo'])
        num_ordenes = int(math.ceil(cant_total / tam_lote_max))
        cant_por_orden = round(cant_total / num_ordenes, 2)

        semana = fila['Semana_Label']
        pref = fila['Centro_Final']

        # Tiempos por unidad según cada centro
        tf_dg = float(fila['Tiempo fabricación unidad DG'] or 0)
        tf_mch = float(fila['Tiempo fabricación unidad MCH'] or 0)

        def horas_lote(centro, cantidad):
            return cantidad * (tf_dg if centro == C1 else tf_mch)

        for _ in range(num_ordenes):
            # Centro preferido (por menor coste)
            centro_asignado = pref
            h_pref = horas_lote(centro_asignado, cant_por_orden)

            # ¿Cabe en el centro preferido?
            if cap_restante.get((centro_asignado, semana), 0.0) >= h_pref:
                cap_restante[(centro_asignado, semana)] -= h_pref
                t_fab = tf_dg if centro_asignado == C1 else tf_mch
                sin_cap = False
            else:
                # Probar en el otro centro
                otro = C2 if centro_asignado == C1 else C1
                h_otro = horas_lote(otro, cant_por_orden)
                if cap_restante.get((otro, semana), 0.0) >= h_otro:
                    centro_asignado = otro
                    cap_restante[(centro_asignado, semana)] -= h_otro
                    t_fab = tf_dg if centro_asignado == C1 else tf_mch
                    sin_cap = False
                else:
                    # Ninguno tiene capacidad -> asignar al preferido y marcar sin capacidad
                    t_fab = tf_dg if centro_asignado == C1 else tf_mch
                    sin_cap = True  # solo informativo (no rompe nada aguas abajo)

            resultado_lotes.append({
                'Nº de propuesta': cont,
                'Material': fila['Material'],
                'Centro': centro_asignado,
                'Clase de orden': 'NORM',
                'Cantidad a fabricar': cant_por_orden,
                'Unidad': fila['Unidad'],
                'Fecha de fabricación': pd.to_datetime(fila['Fecha de necesidad']).strftime('%Y%m%d'),
                'Semana': semana,
                'Horas': cant_por_orden * t_fab,
                # Campo informativo (no lo usas en la exportación final)
                'Sin capacidad (informativo)': sin_cap
            })
            cont += 1

    return pd.DataFrame(resultado_lotes)

# ==========================================
# INTERFAZ PRINCIPAL
# ==========================================
st.markdown("<h1>📊 Sistema de Cálculo de Fabricación</h1>", unsafe_allow_html=True)
st.markdown("Carga los 4 archivos Excel necesarios y ajusta los parámetros de ejecución.")
st.markdown("---")

tab1, tab2 = st.tabs(["📥 Carga de Archivos", "⚙️ Ajuste y Ejecución"])

# Variables de estado para los DataFrames
df_cap, df_mat, df_cli, df_dem = None, None, None, None

# --- TAB 1: CARGA DE ARCHIVOS (Diseño Programa 1) ---
with tab1:
    st.subheader("📁 Carga tus archivos Excel")
    
    col1, col2 = st.columns(2)
    
    # Bloque 1: Capacidad
    with col1:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 🏭 Capacidad de planta")
        file1 = st.file_uploader("Subir Capacidad", type=["xlsx"], key="u1", label_visibility="collapsed")
        if file1:
            try:
                df_cap = pd.read_excel(file1)
                guardar_archivo(file1, "capacidad_planta")
                st.success("✅ Cargado")
                st.dataframe(df_cap, use_container_width=True, height=150)
            except Exception as e: st.error(f"Error: {e}")
        else: st.info("Esperando archivo...")
        st.markdown('</div>', unsafe_allow_html=True)

    # Bloque 2: Maestro Materiales
    with col2:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 📦 Maestro de materiales")
        file2 = st.file_uploader("Subir Materiales", type=["xlsx"], key="u2", label_visibility="collapsed")
        if file2:
            try:
                df_mat = pd.read_excel(file2)
                guardar_archivo(file2, "maestro_materiales")
                st.success("✅ Cargado")
                st.dataframe(df_mat, use_container_width=True, height=400)
            except Exception as e: st.error(f"Error: {e}")
        else: st.info("Esperando archivo...")
        st.markdown('</div>', unsafe_allow_html=True)

    col3, col4 = st.columns(2)
    
    # Bloque 3: Maestro Clientes
    with col3:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 👥 Maestro de clientes")
        file3 = st.file_uploader("Subir Clientes", type=["xlsx"], key="u3", label_visibility="collapsed")
        if file3:
            try:
                df_cli = pd.read_excel(file3)
                guardar_archivo(file3, "maestro_clientes")
                st.success("✅ Cargado")
                st.dataframe(df_cli, use_container_width=True, height=400)
            except Exception as e: st.error(f"Error: {e}")
        else: st.info("Esperando archivo...")
        st.markdown('</div>', unsafe_allow_html=True)

    # Bloque 4: Demanda
    with col4:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 📈 Demanda")
        file4 = st.file_uploader("Subir Demanda", type=["xlsx"], key="u4", label_visibility="collapsed")
        if file4:
            try:
                df_dem = pd.read_excel(file4)
                guardar_archivo(file4, "demanda")
                st.success("✅ Cargado")
                st.dataframe(df_dem, use_container_width=True, height=400)
            except Exception as e: st.error(f"Error: {e}")
        else: st.info("Esperando archivo...")
        st.markdown('</div>', unsafe_allow_html=True)

# --- TAB 2: EJECUCIÓN (Lógica Programa 2) ---
with tab2:
    if df_cap is None or df_mat is None or df_cli is None or df_dem is None:
        st.warning("⚠️ Por favor, carga los 4 archivos en la pestaña anterior para habilitar los ajustes.")
    else:
        # Limpieza de columnas
        for d in [df_cap, df_mat, df_cli, df_dem]: d.columns = d.columns.str.strip()
        
        centros_detectados = [str(c) for c in df_cap['Centro'].unique()]
        df_dem['Semana_Label'] = pd.to_datetime(df_dem['Fecha de necesidad']).dt.strftime('%Y-W%U')
        lista_semanas = sorted(df_dem['Semana_Label'].unique())

        st.subheader("⚙️ Configuración de Porcentajes por Semana")
        c1_name = centros_detectados[0]
        c2_name = centros_detectados[1] if len(centros_detectados) > 1 else "Centro 2"
        
        st.info(f"El sistema priorizará automáticamente el centro más barato. Usa los sliders para definir el reparto en caso de empate técnico entre **{c1_name}** y **{c2_name}**.")

        ajustes = {}
        cols_sliders = st.columns(4)
        for i, sem in enumerate(lista_semanas):
            with cols_sliders[i % 4]:
                ajustes[sem] = st.slider(f"Sem {sem}", 0, 100, 50)

        st.markdown("---")
        if st.button("🚀 EJECUTAR CÁLCULO DE PROPUESTA", use_container_width=True):
            with st.spinner("Calculando asignación óptima de costes..."):
                df_res = procesar_logica_estable(df_dem, df_mat, df_cli, df_cap, ajustes)

                st.success("✅ Cálculo completado con éxito.")
                
                # Métricas
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Propuestas", len(df_res))
                for i, centro in enumerate(centros_detectados):
                    if i == 0:
                        m2.metric(f"Horas Totales {centro}", f"{df_res[df_res['Centro']==centro]['Horas'].sum():,.1f}h")
                    elif i == 1:
                        m3.metric(f"Horas Totales {centro}", f"{df_res[df_res['Centro']==centro]['Horas'].sum():,.1f}h")

                st.subheader("📊 Distribución de Carga Horaria")
                carga_plot = df_res.groupby(['Semana', 'Centro'])['Horas'].sum().unstack().fillna(0)
                st.bar_chart(carga_plot)

                st.subheader("📋 Detalle de la Propuesta")
                st.dataframe(df_res.drop(columns=['Horas']), use_container_width=True)

                # Exportación
                output_path = os.path.join(UPLOAD_DIR, "Propuesta_Final.xlsx")
                df_res.drop(columns=['Semana', 'Horas']).to_excel(output_path, index=False)
                with open(output_path, "rb") as f:
                    st.download_button("📥 Descargar Propuesta en Excel", data=f, file_name=f"Propuesta_Fabricacion_{datetime.now().strftime('%Y%m%d')}.xlsx")

# Footer
st.markdown("---")
st.markdown("""
<div class="footer">
    <p>✨ <strong>Sistema de Cálculo de Fabricación</strong> - Versión 3.2 (Interfaz Unificada)</p>
    <p>Desarrollado con Streamlit | 2026</p>
</div>
""", unsafe_allow_html=True)
