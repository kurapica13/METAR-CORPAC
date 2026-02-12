"""
METAR DIGITAL - VERSIÓN SUPER SIMPLE
Sin errores de importación
"""

import streamlit as st
from datetime import datetime
import pandas as pd
from io import BytesIO

# ============================================
# CONFIGURACIÓN DE PÁGINA
# ============================================
st.set_page_config(
    page_title="METAR Digital",
    page_icon="✈️",
    layout="wide"
)

# ============================================
# INICIALIZAR ESTADO
# ============================================
if 'registros' not in st.session_state:
    st.session_state.registros = []
if 'contador' not in st.session_state:
    st.session_state.contador = 0

# ============================================
# TÍTULO
# ============================================
st.title("✈️ METAR DIGITAL - SPJC")
st.markdown("---")

# ============================================
# FORMULARIO
# ============================================
with st.form("formulario_metar"):
    col1, col2, col3 = st.columns(3)
    with col1:
        dia = st.text_input("Día", datetime.now().strftime("%d"))
    with col2:
        hora = st.text_input("Hora UTC", datetime.now().strftime("%H%M"))
    with col3:
        tipo = st.selectbox("Tipo", ["METAR", "SPECI"])
    
    col1, col2 = st.columns(2)
    with col1:
        dir_viento = st.text_input("Dirección viento", "340")
    with col2:
        int_viento = st.text_input("Intensidad", "15")
    
    var_viento = st.text_input("Variación (opcional)", "")
    vis = st.text_input("Visibilidad", "9999")
    temp = st.text_input("Temperatura", "20")
    rocio = st.text_input("Rocío", "15")
    qnh = st.text_input("QNH", "1013")
    
    generar = st.form_submit_button("🛫 GENERAR METAR")
    
    if generar:
        # Construir METAR
        viento = f"{int(dir_viento):03d}{int(int_viento):02d}KT"
        if var_viento:
            viento = f"{int(dir_viento):03d}{int(int_viento):02d}KT {var_viento}"
        
        metar = f"{tipo} SPJC {dia}{hora}Z {viento} {vis} NSC {int(temp):02d}/{int(rocio):02d} Q{qnh}="
        
        # Guardar
        st.session_state.registros.append({
            'DIA': dia,
            'HORA': hora,
            'TIPO': tipo,
            'METAR': metar
        })
        st.session_state.contador = len(st.session_state.registros)
        
        st.success("✅ METAR generado")
        st.code(metar)

# ============================================
# EXPORTAR
# ============================================
st.markdown("---")
st.subheader("📥 EXPORTAR DATOS")

col1, col2 = st.columns(2)

with col1:
    if st.button("📊 Exportar CSV", use_container_width=True):
        if st.session_state.registros:
            df = pd.DataFrame(st.session_state.registros)
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Descargar CSV",
                data=csv,
                file_name=f"metar_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
            st.success(f"✅ {len(st.session_state.registros)} registros")
        else:
            st.warning("No hay registros")

with col2:
    if st.button("🧹 Limpiar todo", use_container_width=True):
        st.session_state.registros = []
        st.session_state.contador = 0
        st.rerun()

# ============================================
# ESTADÍSTICAS
# ============================================
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("📋 TOTAL REGISTROS", st.session_state.contador)
with col2:
    if st.session_state.registros:
        st.metric("📅 DÍAS", len(set(r['DIA'] for r in st.session_state.registros)))
with col3:
    if st.session_state.registros:
        st.metric("🔄 ÚLTIMA HORA", st.session_state.registros[-1]['HORA'])

# ============================================
# HISTORIAL
# ============================================
if st.session_state.registros:
    st.markdown("---")
    st.subheader("📜 HISTORIAL")
    
    for i, r in enumerate(st.session_state.registros[-10:]):
        if r['TIPO'] == 'SPECI':
            st.markdown(f"<div style='background: #FFE699; padding: 10px; margin: 5px 0; border-radius: 5px;'>{r['METAR']}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='background: #f0f0f0; padding: 10px; margin: 5px 0; border-radius: 5px;'>{r['METAR']}</div>", unsafe_allow_html=True)

# ============================================
# FOOTER
# ============================================
st.markdown("---")
st.markdown("✈️ CORPAC Perú - Aeropuerto Internacional Jorge Chávez (SPJC)")