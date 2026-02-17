"""
METAR DIGITAL - SISTEMA PROFESIONAL CORPAC PERÚ
Aeropuerto Internacional Jorge Chávez (SPJC)
Versión: Final con orden correcto de RMK

Orden del METAR:
[pronóstico/texto fijo] RMK [TN/TX] [texto libre del especialista] [PPXXX] =
"""

import streamlit as st
from datetime import datetime, timezone
import pandas as pd
from pathlib import Path
import re
from io import BytesIO
from decimal import Decimal, ROUND_HALF_UP
import hmac
from enum import Enum

# ============================================
# CONFIGURACIÓN INICIAL
# ============================================
st.set_page_config(
    page_title="METAR SPJC - CORPAC",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================
# CONSTANTES Y ENUMS
# ============================================
class TipoReporte(str, Enum):
    METAR = "METAR"
    SPECI = "SPECI"

class Cuadrante(str, Enum):
    N = "N"; NE = "NE"; E = "E"; SE = "SE"
    S = "S"; SW = "SW"; W = "W"; NW = "NW"

# Catálogo de fenómenos para Lima
FENOMENOS = [
    "FG - Niebla",
    "PRFG - Niebla Parcial",
    "BCFG - Niebla en Bancos",
    "MIFG - Niebla Baja",
    "VCFG - Niebla en la Vecindad",
    "BR - Neblina",
    "-RA - Lluvia Ligera",
    "RA - Lluvia Moderada",
    "+RA - Lluvia Fuerte",
    "-DZ - Llovizna Ligera",
    "DZ - Llovizna Moderada",
    "+DZ - Llovizna Fuerte",
    "SHRA - Chubascos",
    "-SHRA - Chubascos Ligeros",
    "+SHRA - Chubascos Fuertes",
    "TS - Tormenta",
    "-TSRA - Tormenta con Lluvia Ligera",
    "TSRA - Tormenta con Lluvia",
    "+TSRA - Tormenta con Lluvia Fuerte",
    "HZ - Calima",
    "FU - Humo"
]

# Precipitación en formato PPTRZ
PRECIPITACION = {
    "PP000": "Sin precipitación",
    "PPTRZ": "Trazas (< 0.1 mm)",
    "PP001": "0.1 mm",
    "PP002": "0.2 mm",
    "PP003": "0.3 mm",
    "PP004": "0.4 mm",
    "PP005": "0.5 mm",
    "PP006": "0.6 mm",
    "PP007": "0.7 mm",
    "PP008": "0.8 mm",
    "PP009": "0.9 mm",
    "PP010": "1.0 mm"
}

# Tipos de nubes
TIPOS_NUBES = ["CU", "SC", "ST", "AC", "AS", "NS", "CI"]
OCTAS = ["1", "2", "3", "4", "5", "6", "7", "8"]

# Mapeo de octas a códigos METAR
CODIGOS_OCTAS = {
    '1': 'FEW', '2': 'FEW',
    '3': 'SCT', '4': 'SCT',
    '5': 'BKN', '6': 'BKN', '7': 'BKN',
    '8': 'OVC'
}

# ============================================
# DIRECTORIO DE DATOS
# ============================================
DATA_DIR = Path("datos_metar")
DATA_DIR.mkdir(exist_ok=True)

# ============================================
# AUTENTICACIÓN
# ============================================
def autenticar():
    if 'autenticado' not in st.session_state:
        st.session_state.autenticado = False
    
    if st.session_state.autenticado:
        return True
    
    with st.container():
        st.markdown("""
        <style>
        .login-box {
            max-width: 400px;
            margin: 100px auto;
            padding: 30px;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            text-align: center;
            border-top: 4px solid #0b3d91;
        }
        </style>
        """, unsafe_allow_html=True)
        
        st.markdown("<div class='login-box'>", unsafe_allow_html=True)
        st.image("https://upload.wikimedia.org/wikipedia/commons/5/5e/Corpac_logo.png", width=200)
        st.markdown("## Sistema METAR Digital")
        st.markdown("Aeropuerto Internacional Jorge Chávez")
        st.markdown("---")
        
        usuario = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        
        if st.button("INGRESAR", use_container_width=True):
            if usuario == "metar" and password == "spjc2024":
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
        
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

autenticar()

# ============================================
# FUNCIONES DE ARCHIVOS
# ============================================
def nombre_archivo_mes():
    return f"SPJC_METAR_{datetime.now().strftime('%Y_%m')}.xlsx"

def cargar_registros():
    archivo = DATA_DIR / nombre_archivo_mes()
    if archivo.exists():
        try:
            df = pd.read_excel(archivo)
            return df.to_dict('records')
        except:
            return []
    return []

def guardar_registros(registros):
    if not registros:
        return
    
    df = pd.DataFrame(registros)
    archivo = DATA_DIR / nombre_archivo_mes()
    
    with pd.ExcelWriter(archivo, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='METAR SPJC')
        
        # Ajustar ancho de columnas
        worksheet = writer.sheets['METAR SPJC']
        for col in worksheet.columns:
            max_len = 0
            col_letter = col[0].column_letter
            for cell in col:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
            worksheet.column_dimensions[col_letter].width = min(max_len + 2, 50)

# ============================================
# FUNCIONES DE PROCESAMIENTO
# ============================================
def redondear(valor):
    try:
        d = Decimal(str(valor))
        return int(d.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except:
        return int(round(float(valor)))

def procesar_viento(dir, inten, var_desde, var_hasta):
    """Procesa viento según reglas CORPAC"""
    try:
        d = int(dir)
        i = inten.upper().strip()
        
        # Caso especial: calma
        if d == 0 and i == "00":
            return "00000KT"
        
        # Procesar intensidad con posibles ráfagas
        if 'G' in i:
            partes = i.replace('G', ' ').split()
            base = int(partes[0])
            raf = int(partes[1]) if len(partes) > 1 else base
            intensidad = f"{base:02d}G{raf:02d}"
        else:
            intensidad = f"{int(i):02d}"
        
        # Sin variación
        if not var_desde or not var_hasta:
            return f"{d:03d}{intensidad}KT"
        
        # Con variación
        desde = int(var_desde)
        hasta = int(var_hasta)
        
        # Calcular diferencia circular
        diff = min(abs(hasta - desde), 360 - abs(hasta - desde))
        
        if diff < 60:
            return f"{d:03d}{intensidad}KT"
        elif diff >= 180 or int(i) < 3:
            return f"VRB{intensidad}KT"
        else:
            return f"{d:03d}{intensidad}KT {desde:03d}V{hasta:03d}"
            
    except:
        return "/////KT"

def visibilidad_a_metros(vis):
    """Convierte texto de visibilidad a metros"""
    vis = vis.upper().strip()
    
    if vis.endswith("KM"):
        km = float(vis[:-2])
        return 9999 if km >= 10 else int(km * 1000)
    elif vis.endswith("M"):
        return int(vis[:-1])
    else:
        m = int(vis)
        return 9999 if m >= 10000 else m

def visibilidad_minima(texto, vis_principal):
    """Procesa visibilidad mínima con cuadrantes"""
    if not texto:
        return ""
    
    texto = texto.upper().strip()
    
    # Identificar cuadrante
    cuadrante = None
    for q in Cuadrante:
        if texto.endswith(q.value):
            valor = texto[:-len(q.value)]
            cuadrante = q.value
            break
    else:
        valor = texto
    
    try:
        if valor.endswith("KM"):
            m = 9999 if float(valor[:-2]) >= 10 else int(float(valor[:-2]) * 1000)
        elif valor.endswith("M"):
            m = int(valor[:-1])
        else:
            m = int(valor)
            m = 9999 if m >= 10000 else m
        
        # Validar reglas
        if m < 1500 or (m < vis_principal * 0.5 and m < 5000):
            return f"{m:04d}{cuadrante or ''}"
        return ""
    except:
        return ""

def codigo_fenomenos(texto):
    """Convierte texto de fenómenos a código METAR"""
    if not texto:
        return ""
    
    texto = texto.lower()
    codigos = []
    
    # Mapeo de fenómenos comunes
    mapa = {
        "niebla": "FG",
        "niebla parcial": "PRFG",
        "niebla en bancos": "BCFG",
        "niebla baja": "MIFG",
        "niebla en la vecindad": "VCFG",
        "neblina": "BR",
        "lluvia ligera": "-RA",
        "lluvia moderada": "RA",
        "lluvia fuerte": "+RA",
        "llovizna ligera": "-DZ",
        "llovizna moderada": "DZ",
        "llovizna fuerte": "+DZ",
        "chubascos": "SHRA",
        "tormenta": "TS",
        "calima": "HZ",
        "humo": "FU"
    }
    
    for key, value in mapa.items():
        if key in texto:
            codigos.append(value)
    
    return " ".join(codigos[:3])

def procesar_nubes(capas, vv_activo, vv_valor):
    """Procesa nubes a código METAR"""
    if vv_activo:
        if vv_valor == "///":
            return "VV///"
        try:
            return f"VV{round(int(vv_valor)/30):03d}"
        except:
            return "VV///"
    
    if not capas:
        return "NSC"
    
    codigos = []
    for capa in capas[:3]:
        altura = round(int(capa['altura']) / 30)
        altura = min(max(altura, 1), 999)
        cod = f"{CODIGOS_OCTAS[capa['octas']]}{altura:03d}"
        codigos.append(cod)
    
    return " ".join(codigos)

# ============================================
# COMPONENTES FRAGMENT
# ============================================
@st.fragment
def fragment_fenomenos():
    st.markdown("#### Fenómenos")
    
    if 'fenomenos' not in st.session_state:
        st.session_state.fenomenos = []
    
    # Mostrar seleccionados
    for i, fen in enumerate(st.session_state.fenomenos):
        cols = st.columns([10, 1])
        with cols[0]:
            st.info(fen)
        with cols[1]:
            if st.button("✖", key=f"del_fen_{i}"):
                st.session_state.fenomenos.pop(i)
                st.rerun()
    
    # Selector y botón
    cols = st.columns([3, 1])
    with cols[0]:
        nuevo = st.selectbox(
            "Agregar",
            options=[""] + FENOMENOS,
            key="nuevo_fen",
            label_visibility="collapsed"
        )
    with cols[1]:
        if st.button("➕", use_container_width=True):
            if nuevo and nuevo not in st.session_state.fenomenos:
                st.session_state.fenomenos.append(nuevo)
                st.rerun()

@st.fragment
def fragment_nubes():
    st.markdown("#### Nubosidad")
    
    if 'capas_nubes' not in st.session_state:
        st.session_state.capas_nubes = []
    if 'vv_activo' not in st.session_state:
        st.session_state.vv_activo = False
        st.session_state.vv_valor = ""
    
    # Mostrar VV si está activo
    if st.session_state.vv_activo:
        cols = st.columns([8, 1])
        with cols[0]:
            if st.session_state.vv_valor == "///":
                st.info("🌫️ Visibilidad Vertical: DESCONOCIDA (VV///)")
            else:
                cod = f"VV{round(int(st.session_state.vv_valor)/30):03d}"
                st.info(f"🌫️ Visibilidad Vertical: {st.session_state.vv_valor}m ({cod})")
        with cols[1]:
            if st.button("✖", key="del_vv"):
                st.session_state.vv_activo = False
                st.session_state.vv_valor = ""
                st.rerun()
    
    # Mostrar capas
    for i, capa in enumerate(st.session_state.capas_nubes):
        cols = st.columns([2, 2, 3, 1])
        with cols[0]:
            st.write(f"**Capa {i+1}:** {capa['octas']} octas")
        with cols[1]:
            st.write(f"**{capa['tipo']}**")
        with cols[2]:
            st.write(f"**{capa['altura']} m**")
        with cols[3]:
            if st.button("✖", key=f"del_capa_{i}"):
                st.session_state.capas_nubes.pop(i)
                st.rerun()
    
    st.markdown("---")
    
    if not st.session_state.vv_activo:
        tipo = st.radio(
            "Tipo",
            ["Capa de nubes", "Visibilidad Vertical (VV)"],
            horizontal=True,
            key="tipo_nube"
        )
        
        if tipo == "Capa de nubes":
            cols = st.columns([2, 2, 3, 1])
            with cols[0]:
                octa = st.selectbox("Octas", [""] + OCTAS, key="octa")
            with cols[1]:
                tipo_n = st.selectbox("Tipo", [""] + TIPOS_NUBES, key="tipo_n")
            with cols[2]:
                alt = st.text_input("Altura (m)", key="altura", placeholder="300")
            with cols[3]:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("➕", key="add_capa", use_container_width=True):
                    if octa and tipo_n and alt:
                        try:
                            alt_int = int(alt)
                            if 0 < alt_int <= 30000:
                                # Validar regla 1-3-5
                                n = len(st.session_state.capas_nubes) + 1
                                if n == 1 and int(octa) >= 1:
                                    st.session_state.capas_nubes.append({
                                        'octas': octa,
                                        'tipo': tipo_n,
                                        'altura': alt
                                    })
                                    st.rerun()
                                elif n == 2 and int(octa) >= 3:
                                    st.session_state.capas_nubes.append({
                                        'octas': octa,
                                        'tipo': tipo_n,
                                        'altura': alt
                                    })
                                    st.rerun()
                                elif n == 3 and int(octa) >= 5:
                                    st.session_state.capas_nubes.append({
                                        'octas': octa,
                                        'tipo': tipo_n,
                                        'altura': alt
                                    })
                                    st.rerun()
                                elif n > 3:
                                    st.error("Máximo 3 capas")
                                else:
                                    st.error(f"Capa {n} debe tener mínimo {[1,3,5][n-1]} octas")
                            else:
                                st.error("Altura fuera de rango")
                        except:
                            st.error("Altura inválida")
        
        else:  # VV
            cols = st.columns([3, 2, 1])
            with cols[0]:
                vv = st.text_input("Altura VV (m)", key="vv_alt", placeholder="600 o vacío")
            with cols[1]:
                if vv:
                    try:
                        st.markdown(f"**VV{round(int(vv)/30):03d}**")
                    except:
                        st.markdown("**VV///**")
                else:
                    st.markdown("**VV///**")
            with cols[2]:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("➕ VV", key="add_vv", use_container_width=True):
                    if st.session_state.capas_nubes:
                        st.error("No combinar VV con capas")
                    elif not vv:
                        st.session_state.vv_activo = True
                        st.session_state.vv_valor = "///"
                        st.rerun()
                    else:
                        try:
                            vv_int = int(vv)
                            if 0 <= vv_int <= 3000:
                                st.session_state.vv_activo = True
                                st.session_state.vv_valor = str(vv_int)
                                st.rerun()
                            else:
                                st.error("Altura 0-3000m")
                        except:
                            st.error("Valor inválido")

# ============================================
# FUNCIÓN PRINCIPAL DE GENERACIÓN
# ============================================
def generar_metar(datos):
    try:
        # Validaciones básicas
        if not datos['hora'] or len(datos['hora']) != 4:
            raise ValueError("Hora en formato HHMM")
        if not datos['dir_viento'] or not datos['int_viento']:
            raise ValueError("Viento incompleto")
        if not datos['vis']:
            raise ValueError("Visibilidad requerida")
        if not datos['temp'] or not datos['rocio'] or not datos['qnh']:
            raise ValueError("Temperatura, Rocío y QNH requeridos")
        
        # Validar formato de hora (solo formato, no valor)
        if not datos['hora'].isdigit():
            raise ValueError("Hora debe ser numérica")
        
        # Procesar viento
        viento = procesar_viento(
            datos['dir_viento'],
            datos['int_viento'],
            datos['var_desde'],
            datos['var_hasta']
        )
        
        # Procesar visibilidad
        vis_m = visibilidad_a_metros(datos['vis'])
        vis_min = visibilidad_minima(datos['vis_min'], vis_m)
        
        # Procesar otros campos
        rvr = datos['rvr'].strip() if datos['rvr'] else ""
        fenomeno = codigo_fenomenos(" ".join(st.session_state.get('fenomenos', [])))
        nubes = procesar_nubes(
            st.session_state.get('capas_nubes', []),
            st.session_state.get('vv_activo', False),
            st.session_state.get('vv_valor', "")
        )
        
        # Temperaturas
        temp = float(datos['temp'])
        rocio = float(datos['rocio'])
        qnh = int(float(datos['qnh']))
        
        if rocio > temp:
            raise ValueError("Rocío no puede ser mayor que temperatura")
        
        # ===== CONSTRUCCIÓN DEL METAR CON ORDEN CORRECTO =====
        partes = []
        
        # Parte principal del METAR
        partes.append(f"{datos['tipo']} SPJC {datos['dia']}{datos['hora']}Z")
        partes.append(viento)
        partes.append(f"{vis_m:04d}")
        
        if vis_min:
            partes.append(vis_min)
        if rvr:
            partes.append(rvr)
        if fenomeno:
            partes.append(fenomeno)
        
        partes.append(nubes)
        partes.append(f"{redondear(temp):02d}/{redondear(rocio):02d} Q{qnh}")
        
        # 1. PRIMERO: Pronóstico/texto fijo (ANTES de RMK)
        if datos['pronostico']:
            partes.append(datos['pronostico'].upper())
        
        # 2. SEGUNDO: Palabra "RMK"
        partes.append("RMK")
        
        # 3. TERCERO: TN/TX (si aplica)
        if datos['tn_tx']:
            partes.append(datos['tn_tx'])
        
        # 4. CUARTO: Texto libre del especialista
        if datos['texto_libre']:
            partes.append(datos['texto_libre'].upper())
        
        # 5. QUINTO: Precipitación PPXXX (solo si no es PP000)
        if datos['pp'] and datos['pp'] != "PP000":
            partes.append(datos['pp'])
        
        # 6. FINAL: Signo =
        metar = " ".join(partes) + "="
        
        # Calcular HR (opcional)
        def hr_calc():
            try:
                a, b = 17.625, 243.04
                tr = min(rocio, temp)
                es_t = a * temp / (b + temp)
                es_r = a * tr / (b + tr)
                return round(100 * (10**(es_r - es_t)))
            except:
                return ""
        
        registro = {
            'Día': datos['dia'].zfill(2),
            'Hora': datos['hora'],
            'Tipo': datos['tipo'],
            'Dirección_Viento': datos['dir_viento'],
            'Intensidad_Viento': datos['int_viento'],
            'Variación_Viento': f"{datos['var_desde']}V{datos['var_hasta']}" if datos['var_desde'] and datos['var_hasta'] else "",
            'Visibilidad_Original': datos['vis'],
            'Visibilidad_Metros': vis_m,
            'Visibilidad_Mínima': vis_min,
            'RVR': rvr,
            'Fenómeno_Código': fenomeno,
            'Nubes_Código': nubes,
            'Temperatura': temp,
            'Punto_Rocío': rocio,
            'Humedad_Relativa_%': hr_calc(),
            'QNH': qnh,
            'Presión_Estación': datos['presion'],
            'Pronóstico': datos['pronostico'],
            'Texto_Libre': datos['texto_libre'],
            'TN_TX': datos['tn_tx'],
            'Precipitación': datos['pp'],
            'METAR_Completo': metar
        }
        
        return {'success': True, 'metar': metar, 'registro': registro}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

# ============================================
# INICIALIZACIÓN DE ESTADO
# ============================================
if 'registros' not in st.session_state:
    st.session_state.registros = cargar_registros()
if 'historial' not in st.session_state:
    st.session_state.historial = []

# ============================================
# INTERFAZ PRINCIPAL
# ============================================
st.markdown("""
<style>
    .header {
        background: linear-gradient(90deg, #0b3d91 0%, #1a4fa0 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .section {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
        border-left: 4px solid #0b3d91;
    }
    .metar-display {
        background: #1e1e1e;
        color: #00ff00;
        padding: 1rem;
        border-radius: 5px;
        font-family: monospace;
        font-size: 1.1rem;
        border-left: 4px solid #0b3d91;
    }
    .historial-item {
        background: #f8f9fa;
        padding: 0.8rem;
        margin-bottom: 0.5rem;
        border-radius: 5px;
        font-family: monospace;
        font-size: 0.9rem;
        border-left: 3px solid #0b3d91;
    }
    .stButton button {
        border-radius: 5px;
    }
    .info-box {
        background: #e7f3ff;
        padding: 0.5rem;
        border-radius: 5px;
        border-left: 3px solid #0b3d91;
        margin: 0.5rem 0;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class='header'>
    <h1 style='margin:0'>✈️ METAR DIGITAL - SPJC</h1>
    <p style='margin:0; opacity:0.9'>Aeropuerto Internacional Jorge Chávez | CORPAC Perú</p>
</div>
""", unsafe_allow_html=True)

# Layout principal
col1, col2 = st.columns([2, 1])

with col1:
    # Tipo de reporte
    with st.container():
        st.markdown("<div class='section'>", unsafe_allow_html=True)
        st.selectbox(
            "Tipo de Reporte",
            options=[t.value for t in TipoReporte],
            key='tipo'
        )
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Fecha y hora
    with st.container():
        st.markdown("<div class='section'>", unsafe_allow_html=True)
        cols = st.columns(2)
        with cols[0]:
            st.text_input("Día", key='dia', value=datetime.now().strftime("%d"), placeholder="01-31")
        with cols[1]:
            st.text_input("Hora (UTC)", key='hora', value=datetime.now().strftime("%H%M"), placeholder="HHMM")
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Viento
    with st.container():
        st.markdown("<div class='section'>", unsafe_allow_html=True)
        st.markdown("#### Viento")
        cols = st.columns([2, 2, 1, 2, 2])
        with cols[0]:
            st.text_input("Dirección", key='dir_viento', placeholder="360")
        with cols[1]:
            st.text_input("Intensidad", key='int_viento', placeholder="15")
        with cols[2]:
            st.markdown("<br><b>-</b>", unsafe_allow_html=True)
        with cols[3]:
            st.text_input("Desde", key='var_desde', placeholder="340")
        with cols[4]:
            st.text_input("Hasta", key='var_hasta', placeholder="080")
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Visibilidad
    with st.container():
        st.markdown("<div class='section'>", unsafe_allow_html=True)
        st.markdown("#### Visibilidad")
        cols = st.columns(3)
        with cols[0]:
            st.text_input("Visibilidad", key='vis', placeholder="10km, 5000m, 9999")
        with cols[1]:
            st.text_input("Visibilidad Mínima", key='vis_min', placeholder="1200SW")
        with cols[2]:
            st.text_input("RVR", key='rvr', placeholder="R32/0400")
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Fenómenos (fragment)
    with st.container():
        st.markdown("<div class='section'>", unsafe_allow_html=True)
        fragment_fenomenos()
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Nubes (fragment)
    with st.container():
        st.markdown("<div class='section'>", unsafe_allow_html=True)
        fragment_nubes()
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Temperatura y presión
    with st.container():
        st.markdown("<div class='section'>", unsafe_allow_html=True)
        st.markdown("#### Temperatura y Presión")
        cols = st.columns(4)
        with cols[0]:
            st.text_input("Temp °C", key='temp', placeholder="-10/40")
        with cols[1]:
            st.text_input("Rocío °C", key='rocio', placeholder="≤ Temp")
        with cols[2]:
            st.text_input("QNH hPa", key='qnh', placeholder="850-1100")
        with cols[3]:
            st.text_input("Presión Est.", key='presion', placeholder="Opcional")
        st.markdown("</div>", unsafe_allow_html=True)
    
    # ===== INFORMACIÓN SUPLEMENTARIA - DOS CAMPOS =====
    with st.container():
        st.markdown("<div class='section'>", unsafe_allow_html=True)
        st.markdown("#### Información Suplementaria")
        
        st.markdown("**📋 Pronóstico / Texto fijo (VA ANTES de RMK):**")
        pronostico = st.text_input(
            "##", 
            key="pronostico", 
            placeholder="Ej: NOSIG, BECMG FM1200 9999 NSW, etc.",
            label_visibility="collapsed"
        )
        st.markdown("<div class='info-box'>Este texto va ANTES de la palabra RMK</div>", unsafe_allow_html=True)
        
        st.markdown("**✏️ Texto libre del especialista (VA DESPUÉS de RMK):**")
        texto_libre = st.text_input(
            "##", 
            key="texto_libre", 
            placeholder="Ej: CB AL NE, TORRE VISUAL, etc.",
            label_visibility="collapsed"
        )
        st.markdown("<div class='info-box'>Este texto va DESPUÉS de RMK y TN/TX</div>", unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    # TN/TX según hora
    hora_actual = int(datetime.now().strftime("%H%M"))
    tn_tx_valor = None
    
    if 1200 <= hora_actual < 1300:
        with st.container():
            st.markdown("<div class='section'>", unsafe_allow_html=True)
            st.markdown("#### 📉 TN (Temperatura Mínima 12Z)")
            tn_valor = st.text_input("Valor TN °C", key="tn_valor", placeholder="Ej: 18.5")
            if tn_valor:
                tn_tx_valor = f"TN{tn_valor}/1200Z"
            st.markdown("</div>", unsafe_allow_html=True)
    elif 2200 <= hora_actual < 2300:
        with st.container():
            st.markdown("<div class='section'>", unsafe_allow_html=True)
            st.markdown("#### 📈 TX (Temperatura Máxima 22Z)")
            tx_valor = st.text_input("Valor TX °C", key="tx_valor", placeholder="Ej: 25.5")
            if tx_valor:
                tn_tx_valor = f"TX{tx_valor}/2200Z"
            st.markdown("</div>", unsafe_allow_html=True)
    
    # Precipitación
    with st.container():
        st.markdown("<div class='section'>", unsafe_allow_html=True)
        st.markdown("#### Precipitación (PP)")
        pp = st.selectbox(
            "##",
            options=list(PRECIPITACION.keys()),
            format_func=lambda x: f"{x} - {PRECIPITACION[x]}",
            key="pp",
            label_visibility="collapsed"
        )
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Botón generar
    col_b1, col_b2, col_b3 = st.columns([1, 2, 1])
    with col_b2:
        if st.button("🎯 GENERAR METAR", use_container_width=True, type="primary"):
            datos = {
                'tipo': st.session_state.tipo,
                'dia': st.session_state.dia,
                'hora': st.session_state.hora,
                'dir_viento': st.session_state.dir_viento,
                'int_viento': st.session_state.int_viento,
                'var_desde': st.session_state.get('var_desde', ''),
                'var_hasta': st.session_state.get('var_hasta', ''),
                'vis': st.session_state.vis,
                'vis_min': st.session_state.vis_min,
                'rvr': st.session_state.rvr,
                'temp': st.session_state.temp,
                'rocio': st.session_state.rocio,
                'qnh': st.session_state.qnh,
                'presion': st.session_state.presion,
                'pronostico': st.session_state.pronostico,
                'texto_libre': st.session_state.texto_libre,
                'pp': pp,
                'tn_tx': tn_tx_valor
            }
            
            resultado = generar_metar(datos)
            
            if resultado['success']:
                # Actualizar registros
                hora_clave = f"{datos['dia']}_{datos['hora']}"
                encontrado = False
                for i, reg in enumerate(st.session_state.registros):
                    if f"{reg.get('Día','')}_{reg.get('Hora','')}" == hora_clave:
                        st.session_state.registros[i] = resultado['registro']
                        encontrado = True
                        break
                
                if not encontrado:
                    st.session_state.registros.insert(0, resultado['registro'])
                
                # Guardar
                guardar_registros(st.session_state.registros)
                
                # Actualizar historial
                st.session_state.historial.insert(0, resultado['metar'])
                st.session_state.historial = st.session_state.historial[:15]
                
                # Guardar último para mostrar
                st.session_state.ultimo_metar = resultado['metar']
                
                st.success(f"✅ METAR generado correctamente ({datos['hora']}Z)")
                st.rerun()
            else:
                st.error(f"❌ {resultado['error']}")

with col2:
    # Último METAR
    st.markdown("### 📋 Último METAR")
    if 'ultimo_metar' in st.session_state:
        st.markdown(f"<div class='metar-display'>{st.session_state.ultimo_metar}</div>", unsafe_allow_html=True)
    else:
        st.info("No hay METAR generado")
    
    # Estadísticas
    st.markdown("---")
    st.markdown("### 📊 Estadísticas")
    st.metric("Registros del mes", len(st.session_state.registros))
    
    # Exportar
    if st.button("📥 Exportar Excel", use_container_width=True):
        if st.session_state.registros:
            guardar_registros(st.session_state.registros)
            archivo = DATA_DIR / nombre_archivo_mes()
            with open(archivo, 'rb') as f:
                st.download_button(
                    label="✅ Descargar",
                    data=f,
                    file_name=nombre_archivo_mes(),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
        else:
            st.warning("No hay datos")
    
    # Limpiar memoria
    if st.button("🗑️ Limpiar memoria", use_container_width=True):
        st.session_state.registros = []
        st.session_state.historial = []
        if 'ultimo_metar' in st.session_state:
            del st.session_state.ultimo_metar
        st.success("Memoria limpiada")
        st.rerun()
    
    # Historial
    st.markdown("---")
    st.markdown("### 📜 Historial")
    if st.session_state.historial:
        for metar in st.session_state.historial[:8]:
            clase = "historial-item"
            if "SPECI" in metar:
                st.markdown(f"<div style='background:#FFE699; padding:0.8rem; margin-bottom:0.5rem; border-radius:5px; font-family:monospace; border-left:3px solid #FFC000;'>{metar}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='historial-item'>{metar}</div>", unsafe_allow_html=True)
    else:
        st.info("Sin historial")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align:center; color:#666; padding:1rem; font-size:0.8rem;'>
    METAR Digital - Sistema Profesional CORPAC Perú<br>
    Aeropuerto Internacional Jorge Chávez (SPJC)<br>
    Orden: [pronóstico] RMK [TN/TX] [texto libre] [PP] =
</div>
""", unsafe_allow_html=True)