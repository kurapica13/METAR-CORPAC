"""
METAR DIGITAL WEB - VERSIÓN PROFESIONAL CORPAC PERÚ
Aeropuerto Internacional Jorge Chávez (SPJC)
Versión ESTABLE - Sin errores de caché
"""

import streamlit as st
from datetime import datetime
import pandas as pd
import re
from io import BytesIO

# ============================================
# CONFIGURACIÓN DE PÁGINA
# ============================================
st.set_page_config(
    page_title="METAR Digital - CORPAC Perú",
    page_icon="✈️",
    layout="wide"
)

# ============================================
# LIMPIAR CACHÉ AL INICIAR
# ============================================
st.cache_data.clear()
st.cache_resource.clear()

# ============================================
# INICIALIZAR ESTADO DE SESIÓN
# ============================================
if 'registros' not in st.session_state:
    st.session_state.registros = []
if 'historial' not in st.session_state:
    st.session_state.historial = []
if 'contador' not in st.session_state:
    st.session_state.contador = 0
if 'dia_actual' not in st.session_state:
    st.session_state.dia_actual = datetime.now().strftime("%d")

# ============================================
# FUNCIONES DE PROCESAMIENTO - VIENTO
# ============================================
def procesar_viento(direccion, intensidad, variacion):
    """Procesa viento con reglas circulares CORPAC"""
    try:
        dir_int = int(direccion)
        int_str = str(intensidad).upper().strip()
        
        # Procesar intensidad
        if 'G' in int_str:
            if 'G' in int_str and ' ' not in int_str.replace('G', ''):
                base, gust = int_str.split('G')
                int_base = int(base)
                int_gust = int(gust)
                int_metar = f"{int_base:02d}G{int_gust:02d}"
            else:
                parts = int_str.replace('G', ' ').split()
                int_base = int(parts[0])
                int_gust = int(parts[1])
                int_metar = f"{int_base:02d}G{int_gust:02d}"
        else:
            int_base = int(int_str)
            int_metar = f"{int_base:02d}"
        
        # Sin variación
        if not variacion:
            return f"{dir_int:03d}{int_metar}KT"
        
        # Con variación
        variacion = variacion.upper().replace(' ', '')
        if 'V' not in variacion:
            return f"{dir_int:03d}{int_metar}KT"
        
        desde, hasta = map(int, variacion.split('V'))
        diff1 = abs(hasta - desde)
        diff2 = 360 - diff1
        diferencia = min(diff1, diff2)
        
        # Reglas CORPAC
        if diferencia >= 180:
            return f"VRB{int_metar}KT"
        
        if diferencia >= 60:
            if int_base < 3:
                return f"VRB{int_metar}KT"
            else:
                if diff1 <= 180:
                    return f"{dir_int:03d}{int_metar}KT {desde:03d}V{hasta:03d}"
                else:
                    return f"{dir_int:03d}{int_metar}KT {hasta:03d}V{desde:03d}"
        
        return f"{dir_int:03d}{int_metar}KT {variacion}"
    
    except:
        return f"{direccion.zfill(3)}{intensidad}KT"

# ============================================
# FUNCIONES DE PROCESAMIENTO - VISIBILIDAD
# ============================================
def convertir_visibilidad(vis_texto):
    """Convierte visibilidad a metros"""
    vis_texto = vis_texto.strip().upper()
    if not vis_texto:
        return 9999
    
    try:
        if vis_texto.endswith("KM"):
            km = float(vis_texto[:-2])
            return 9999 if km >= 10 else int(km * 1000)
        elif vis_texto.endswith("M"):
            return int(vis_texto[:-1])
        else:
            metros = int(vis_texto)
            return 9999 if metros >= 10000 else metros
    except:
        return 9999

def procesar_visibilidad_minima(vis_min_texto, vis_m):
    """Procesa visibilidad mínima con cuadrantes - CORREGIDO"""
    if not vis_min_texto:
        return ""
    
    vis_min_texto = vis_min_texto.strip().upper()
    
    # Priorizar cuadrantes de 2 letras
    if vis_min_texto.endswith('NW'):
        valor = vis_min_texto[:-2]
        cuadrante = 'NW'
    elif vis_min_texto.endswith('NE'):
        valor = vis_min_texto[:-2]
        cuadrante = 'NE'
    elif vis_min_texto.endswith('SW'):
        valor = vis_min_texto[:-2]
        cuadrante = 'SW'
    elif vis_min_texto.endswith('SE'):
        valor = vis_min_texto[:-2]
        cuadrante = 'SE'
    elif vis_min_texto.endswith('N'):
        valor = vis_min_texto[:-1]
        cuadrante = 'N'
    elif vis_min_texto.endswith('S'):
        valor = vis_min_texto[:-1]
        cuadrante = 'S'
    elif vis_min_texto.endswith('E'):
        valor = vis_min_texto[:-1]
        cuadrante = 'E'
    elif vis_min_texto.endswith('W'):
        valor = vis_min_texto[:-1]
        cuadrante = 'W'
    else:
        valor = vis_min_texto
        cuadrante = ''
    
    try:
        if valor.endswith("KM"):
            km = float(valor[:-2])
            vis_min_m = 9999 if km >= 10 else int(km * 1000)
        elif valor.endswith("M"):
            vis_min_m = int(valor[:-1])
        else:
            vis_min_m = int(valor)
            vis_min_m = 9999 if vis_min_m >= 10000 else vis_min_m
        
        # Validar reglas CORPAC
        es_valida = False
        if vis_min_m < 1500:
            es_valida = True
        if vis_min_m < (vis_m * 0.5) and vis_min_m < 5000:
            es_valida = True
        
        if not es_valida:
            return ""
        
        if cuadrante:
            return f"{vis_min_m:04d}{cuadrante}"
        else:
            return f"{vis_min_m:04d}"
    
    except:
        return ""

def procesar_rvr(rvr_texto):
    """Procesa RVR"""
    if not rvr_texto:
        return ""
    
    rvr_texto = rvr_texto.strip().upper().replace('M', '').replace('RVR', '')
    
    try:
        rvr_valor = int(rvr_texto)
        if 50 <= rvr_valor <= 2000:
            return f"RVR{rvr_valor:04d}"
        return ""
    except:
        return ""

# ============================================
# FUNCIONES DE PROCESAMIENTO - FENÓMENOS
# ============================================
def codificar_fenomenos(texto):
    """Codifica fenómenos meteorológicos"""
    if not texto:
        return ""
    
    texto_lower = texto.lower().strip()
    
    # Fenómenos especiales de niebla
    if any(x in texto_lower for x in ["niebla parcial", "prfg", "pr fg", "parcial"]):
        return "PRFG"
    if any(x in texto_lower for x in ["niebla en la vecindad", "vcfg", "vc fg", "vecindad"]):
        return "VCFG"
    if any(x in texto_lower for x in ["niebla en bancos", "bcfg", "bc fg", "bancos"]):
        return "BCFG"
    if any(x in texto_lower for x in ["niebla baja", "mifg", "mi fg", "baja"]):
        return "MIFG"
    
    # Mapeo simple
    mapeo = {
        "lluvia": "RA", "llovizna": "DZ", "niebla": "FG", "neblina": "BR",
        "nieve": "SN", "granizo": "GR", "tormenta": "TS", "polvo": "DU",
        "arena": "SA", "humo": "FU", "ceniza": "VA", "calima": "HZ"
    }
    
    for key, value in mapeo.items():
        if key in texto_lower:
            if "ligera" in texto_lower or "ligero" in texto_lower:
                return f"-{value}"
            if "fuerte" in texto_lower or "intensa" in texto_lower:
                return f"+{value}"
            return value
    
    return ""

# ============================================
# FUNCIONES DE NUBES
# ============================================
def interpretar_nubes(texto, vis_m, fenomeno):
    """Interpreta nubes a código METAR"""
    texto = texto.strip().upper()
    
    if not texto or texto in ["DESPEJADO", "SKC", "CLR", "NSC", "SIN NUBES"]:
        if vis_m >= 9999 and not fenomeno:
            return "CAVOK"
        return "NSC"
    
    return "NSC"  # Simplificado para esta versión

# ============================================
# FUNCIÓN PRINCIPAL DE GENERACIÓN
# ============================================
def generar_metar(datos):
    """Genera código METAR"""
    try:
        # Validaciones básicas
        if not datos['dir_viento'] or not datos['int_viento']:
            raise ValueError("Dirección e intensidad del viento son obligatorias")
        if not datos['vis']:
            raise ValueError("Visibilidad es obligatoria")
        if not datos['temp'] or not datos['rocio'] or not datos['qnh']:
            raise ValueError("Temperatura, Rocío y QNH son obligatorios")
        
        # Procesar
        hora = datos['hora'].zfill(4)
        viento = procesar_viento(datos['dir_viento'], datos['int_viento'], datos['var_viento'])
        vis_m = convertir_visibilidad(datos['vis'])
        vis_min = procesar_visibilidad_minima(datos['vis_min'], vis_m)
        rvr = procesar_rvr(datos['rvr'])
        fenomeno = codificar_fenomenos(datos['fenomeno'])
        nubes = interpretar_nubes(datos['nubes'], vis_m, fenomeno)
        
        # Construir METAR
        metar = f"{datos['tipo']} SPJC {datos['dia']}{hora}Z {viento}"
        
        if nubes == "CAVOK":
            metar += " CAVOK"
        else:
            metar += f" {vis_m:04d}"
            if vis_min:
                metar += f" {vis_min}"
            if rvr:
                metar += f" {rvr}"
            if fenomeno:
                metar += f" {fenomeno}"
            metar += f" {nubes}"
        
        metar += f" {int(float(datos['temp'])):02d}/{int(float(datos['rocio'])):02d} Q{int(float(datos['qnh']))}="
        
        if datos['suplementaria']:
            metar += f" {datos['suplementaria'].upper()}"
        
        # Registrar
        registro = {
            'Día': datos['dia'],
            'Hora': hora,
            'Tipo': datos['tipo'],
            'METAR': metar,
            'Viento': viento,
            'Visibilidad': vis_m,
            'Visibilidad Mínima': vis_min,
            'RVR': rvr,
            'Fenómeno': fenomeno,
            'Nubes': nubes,
            'Temp': datos['temp'],
            'Rocío': datos['rocio'],
            'QNH': datos['qnh']
        }
        
        return {'success': True, 'metar': metar, 'registro': registro}
    
    except Exception as e:
        return {'success': False, 'error': str(e)}

# ============================================
# INTERFAZ DE USUARIO
# ============================================
st.title("✈️ METAR DIGITAL - SPJC")
st.markdown("**Aeropuerto Internacional Jorge Chávez - CORPAC Perú**")
st.markdown("---")

# Columnas
col_izq, col_der = st.columns([2, 1])

with col_izq:
    with st.form("metar_form"):
        st.subheader("📋 DATOS DEL REPORTE")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            dia = st.text_input("Día", value=st.session_state.dia_actual, key='dia')
            st.session_state.dia_actual = dia
        with col2:
            hora = st.text_input("Hora UTC", value=datetime.now().strftime("%H%M"), key='hora')
        with col3:
            tipo = st.selectbox("Tipo", ["METAR", "SPECI"], key='tipo')
        
        st.markdown("---")
        st.subheader("💨 VIENTO")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            dir_viento = st.text_input("Dirección (0-360)", key='dir_viento')
        with col2:
            int_viento = st.text_input("Intensidad (KT)", key='int_viento', help="Ej: 15 o 15G25")
        with col3:
            var_viento = st.text_input("Variación", key='var_viento', help="Ej: 340V080")
        
        st.markdown("---")
        st.subheader("👁️ VISIBILIDAD")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            vis = st.text_input("Visibilidad", key='vis', help="Ej: 9999, 5000M, 10KM")
        with col2:
            vis_min = st.text_input("Visibilidad Mínima", key='vis_min', help="Ej: 1200SW, 1500SE, 0800NE")
        with col3:
            rvr = st.text_input("RVR", key='rvr', help="Ej: 0600, 1200")
        
        st.markdown("---")
        st.subheader("☁️ FENÓMENOS Y NUBES")
        
        fenomeno = st.text_input("Fenómeno", key='fenomeno', help="Ej: niebla parcial, lluvia ligera")
        nubes = st.text_input("Nubes", key='nubes', help="Ej: NSC, CAVOK")
        
        st.markdown("---")
        st.subheader("🌡️ TEMPERATURA Y PRESIÓN")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            temp = st.text_input("Temperatura °C", key='temp')
        with col2:
            rocio = st.text_input("Rocío °C", key='rocio')
        with col3:
            qnh = st.text_input("QNH hPa", key='qnh')
        
        st.markdown("---")
        suplementaria = st.text_input("📝 Información Suplementaria", key='suplementaria', 
                                     help="Ej: RMK CB AL NE")
        
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            generar = st.form_submit_button("🛫 GENERAR METAR", use_container_width=True)
        with col2:
            limpiar = st.form_submit_button("🧹 LIMPIAR CAMPOS", use_container_width=True)
        
        if limpiar:
            for key in ['dir_viento', 'int_viento', 'var_viento', 'vis', 'vis_min', 
                       'rvr', 'fenomeno', 'nubes', 'temp', 'rocio', 'qnh', 'suplementaria']:
                if key in st.session_state:
                    st.session_state[key] = ""
            st.rerun()
        
        if generar:
            datos = {
                'tipo': tipo, 'dia': dia, 'hora': hora,
                'dir_viento': dir_viento, 'int_viento': int_viento, 'var_viento': var_viento,
                'vis': vis, 'vis_min': vis_min, 'rvr': rvr,
                'fenomeno': fenomeno, 'nubes': nubes,
                'temp': temp, 'rocio': rocio, 'qnh': qnh,
                'suplementaria': suplementaria
            }
            
            resultado = generar_metar(datos)
            
            if resultado['success']:
                # Evitar duplicados
                clave = f"{resultado['registro']['Día']}_{resultado['registro']['Hora']}"
                st.session_state.registros = [r for r in st.session_state.registros 
                                            if f"{r['Día']}_{r['Hora']}" != clave]
                st.session_state.registros.insert(0, resultado['registro'])
                
                # Historial
                st.session_state.historial.insert(0, resultado['metar'])
                st.session_state.contador = len(st.session_state.registros)
                
                st.success("✅ METAR generado correctamente")
                if len(st.session_state.registros) > 0 and st.session_state.registros[0]['Día'] == dia:
                    st.info(f"📅 Día de observación: {dia}")
                
                st.session_state.ultimo_metar = resultado['metar']
                st.session_state.ultimo_tipo = tipo
            else:
                st.error(f"❌ {resultado['error']}")

with col_der:
    st.subheader("📊 METAR GENERADO")
    if 'ultimo_metar' in st.session_state:
        if st.session_state.get('ultimo_tipo') == "SPECI":
            st.markdown(f"<div style='background: #FFE699; padding: 15px; border-radius: 5px; font-family: monospace; border-left: 5px solid #FFC000;'><b>⚠️ SPECI</b><br>{st.session_state.ultimo_metar}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='background: #1e1e1e; color: #00ff00; padding: 15px; border-radius: 5px; font-family: monospace; border-left: 5px solid #0b3d91;'>{st.session_state.ultimo_metar}</div>", unsafe_allow_html=True)
    else:
        st.info("---")
    
    st.markdown("---")
    st.subheader("💾 EXPORTAR")
    
    if st.button("📥 Exportar Excel", use_container_width=True):
        if st.session_state.registros:
            try:
                df = pd.DataFrame(st.session_state.registros)
                output = BytesIO()
                df.to_excel(output, index=False, engine='openpyxl')
                output.seek(0)
                
                fecha = datetime.now().strftime("%Y_%m")
                st.download_button(
                    label="📥 Descargar Excel",
                    data=output,
                    file_name=f"SPJC_METAR_{fecha}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                st.success(f"✅ {len(st.session_state.registros)} registros exportados")
            except Exception as e:
                # Fallback a CSV
                df = pd.DataFrame(st.session_state.registros)
                csv = df.to_csv(index=False)
                st.download_button(
                    label="📥 Descargar CSV (fallback)",
                    data=csv,
                    file_name=f"SPJC_METAR_{fecha}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                st.warning("⚠️ Se exportó en CSV (Excel no disponible)")
        else:
            st.warning("⚠️ No hay registros")
    
    st.markdown("---")
    st.metric("📋 REGISTROS EN MEMORIA", st.session_state.contador)
    
    if st.button("🗑️ Limpiar Todo", use_container_width=True):
        st.session_state.registros = []
        st.session_state.historial = []
        st.session_state.contador = 0
        st.success("✅ Memoria limpiada")
        st.rerun()
    
    st.markdown("---")
    st.subheader("📜 HISTORIAL")
    
    if st.session_state.historial:
        for metar in st.session_state.historial[:5]:
            if "SPECI" in metar:
                st.markdown(f"<div style='background: #FFE699; padding: 8px; margin-bottom: 5px; border-radius: 3px; font-family: monospace; font-size: 12px; border-left: 3px solid #FFC000;'>{metar[:70]}...</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='background: #f0f0f0; padding: 8px; margin-bottom: 5px; border-radius: 3px; font-family: monospace; font-size: 12px; border-left: 3px solid #0b3d91;'>{metar[:70]}...</div>", unsafe_allow_html=True)
    else:
        st.info("No hay METARs en el historial")

# ============================================
# FOOTER
# ============================================
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>✈️ METAR Digital - CORPAC Perú | Aeropuerto Internacional Jorge Chávez (SPJC)</p>
    <p style='font-size: 0.8rem;'>✓ Viento Circular ✓ Visibilidad Mínima con Cuadrantes ✓ RVR ✓ Sin Duplicados ✓ Día Corregido</p>
</div>
""", unsafe_allow_html=True)