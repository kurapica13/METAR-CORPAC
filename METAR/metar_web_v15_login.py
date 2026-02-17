"""
METAR DIGITAL - VERSIÓN PROFESIONAL CORPAC PERÚ
Aeropuerto Internacional Jorge Chávez (SPJC)
Versión 17.0 - VERSIÓN SIMPLIFICADA (SIN VALIDACIÓN DE HORA)

Características:
✅ Hora libre - El operador ingresa la hora que corresponde
✅ TN/TX simplificado - TN 12Z, TX 22Z (solo valor numérico)
✅ PP000 agregado - Para cuando no hay precipitación
✅ Orden correcto: Fenómenos → Nubes → Temp/Presión → Suplementaria → TN/TX → Precipitación
✅ Viento con 4 campos - Dirección, intensidad, variación desde/hasta
✅ Fenómenos con botón "➕ Agregar Fenómeno"
✅ Nubes con validación 1-3-5 y VV
✅ Formato PPTRZ completo (PP000 a PP010)
✅ Interfaz compacta y profesional
"""

import streamlit as st
from datetime import datetime, timezone
import pandas as pd
from pathlib import Path
import re
import os
from io import BytesIO
from decimal import Decimal, ROUND_HALF_UP
import hmac
from enum import Enum

# ============================================
# CONFIGURACIÓN DE PÁGINA
# ============================================
st.set_page_config(
    page_title="REGISTRO METAR/SPECI SPJC",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================
# ENUMS PARA CONSTANTES
# ============================================
class TipoReporte(str, Enum):
    METAR = "METAR"
    SPECI = "SPECI"

class Cuadrante(str, Enum):
    N = "N"; NE = "NE"; E = "E"; SE = "SE"
    S = "S"; SW = "SW"; W = "W"; NW = "NW"

# ============================================
# LISTA COMPLETA DE FENÓMENOS PARA LIMA (SPJC)
# ============================================
FENOMENOS_LIMA = {
    "Nieblas": ["FG - Niebla", "PRFG - Niebla Parcial", "BCFG - Niebla en Bancos", 
                "MIFG - Niebla Baja", "VCFG - Niebla en la Vecindad"],
    "Nieblinas": ["BR - Neblina"],
    "Precipitación": ["-RA - Lluvia Ligera", "RA - Lluvia Moderada", "+RA - Lluvia Fuerte",
                     "-DZ - Llovizna Ligera", "DZ - Llovizna Moderada", "+DZ - Llovizna Fuerte",
                     "SHRA - Chubascos de Lluvia", "-SHRA - Chubascos Ligeros", "+SHRA - Chubascos Fuertes"],
    "Tormentas": ["TS - Tormenta", "-TSRA - Tormenta con Lluvia Ligera", 
                  "TSRA - Tormenta con Lluvia", "+TSRA - Tormenta con Lluvia Fuerte"],
    "Otros": ["HZ - Calima", "FU - Humo", "DU - Polvo", "SA - Arena", "VA - Ceniza Volcánica"]
}

# Opciones de precipitación en formato PPTRZ (CON PP000)
OPCIONES_PP = {
    "PP000": "Sin precipitación (0.0 mm)",
    "PPTRZ": "Trazas (< 0.1 mm)",
    "PP001": "0.1 mm", "PP002": "0.2 mm", "PP003": "0.3 mm",
    "PP004": "0.4 mm", "PP005": "0.5 mm", "PP006": "0.6 mm",
    "PP007": "0.7 mm", "PP008": "0.8 mm", "PP009": "0.9 mm",
    "PP010": "1.0 mm"
}

# Tipos de nubes y octas
TIPOS_NUBES = ["CU", "SC", "ST", "AC", "AS", "NS", "CI", "CB", "TCU"]
OCTAS = ["1", "2", "3", "4", "5", "6", "7", "8"]

# Mapeo de octas a códigos METAR
MAPEO_OCTAS = {'1': 'FEW', '2': 'FEW', '3': 'SCT', '4': 'SCT',
               '5': 'BKN', '6': 'BKN', '7': 'BKN', '8': 'OVC'}

# ============================================
# SISTEMA DE AUTENTICACIÓN
# ============================================
def verificar_autenticacion():
    if 'autenticado' not in st.session_state:
        st.session_state.autenticado = False
        st.session_state.usuario = None
    
    with st.sidebar:
        if st.session_state.autenticado:
            st.markdown(f"👤 **Usuario:** {st.session_state.usuario}")
            if st.button("🚪 Cerrar Sesión", use_container_width=True):
                st.session_state.autenticado = False
                st.session_state.usuario = None
                st.rerun()
            st.markdown("---")
    
    if st.session_state.autenticado:
        return True
    
    st.markdown("""
    <style>
    .login-container{max-width:400px;margin:100px auto;padding:30px;background:var(--background-color);border-radius:10px;text-align:center;border:1px solid rgba(128,128,128,0.2);}
    .login-header{color:#0b3d91;margin-bottom:20px;}.login-logo{font-size:48px;margin-bottom:10px;}
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<div class='login-container'>", unsafe_allow_html=True)
    st.markdown("<div class='login-logo'>✈️</div>")
    st.markdown("<h2 class='login-header'>Sistema METAR Digital</h2>")
    st.markdown("Aeropuerto Internacional Jorge Chávez")
    st.markdown("CORPAC Perú")
    st.markdown("---")
    
    with st.form("login_form"):
        usuario = st.text_input("Usuario")
        contraseña = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("🔐 INGRESAR", use_container_width=True)
    
    if submit:
        try:
            passwords = st.secrets.get("passwords", {"admin": "corpac2024", "metar": "spjc2024"})
        except:
            passwords = {"admin": "corpac2024", "metar": "spjc2024"}
        
        if usuario in passwords and hmac.compare_digest(contraseña, passwords[usuario]):
            st.session_state.autenticado = True
            st.session_state.usuario = usuario
            st.rerun()
        else:
            st.error("❌ Usuario o contraseña incorrectos")
    
    st.markdown("---")
    st.markdown("Solo personal autorizado CORPAC")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

verificar_autenticacion()

# ============================================
# CONSTANTES Y CONFIGURACIÓN
# ============================================
DIRECTORIO_DATOS = Path("datos_metar")
DIRECTORIO_DATOS.mkdir(exist_ok=True)

# ============================================
# FUNCIÓN DE REDONDEO
# ============================================
def redondear_metar(valor):
    try:
        d = Decimal(str(valor))
        return int(d.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except:
        return int(round(float(valor)))

# ============================================
# FUNCIONES DE UTILIDAD
# ============================================
def calcular_hr_automatica(temp_c, rocio_c):
    try:
        a, b = 17.625, 243.04
        rocio_c = min(rocio_c, temp_c)
        es_temp = a * temp_c / (b + temp_c)
        es_rocio = a * rocio_c / (b + rocio_c)
        hr = 100 * (10**(es_rocio - es_temp))
        return round(min(max(hr, 0), 100))
    except:
        return None

# ============================================
# ESTILOS CSS PERSONALIZADOS
# ============================================
st.markdown("""
<style>
    .stApp { background-color: var(--background-color); }
    .section-title { color: #0b3d91 !important; font-weight: 700 !important; 
                    font-size: 1.1rem !important; border-bottom: 2px solid #0b3d91 !important; 
                    padding-bottom: 0.3rem !important; margin: 0.5rem 0 !important; }
    .stTextInput label, .stSelectbox label { color: #0b3d91 !important; font-weight: 600 !important; }
    @media (prefers-color-scheme: dark) {
        .stTextInput label, .stSelectbox label { color: #6ab0ff !important; }
        .section-title { color: #6ab0ff !important; border-bottom-color: #6ab0ff !important; }
    }
    .metar-box { background: #1e1e1e; color: #00ff00; padding: 1rem; border-radius: 5px; 
                font-family: 'Courier New', monospace; font-size: 1rem; border-left: 5px solid #0b3d91; }
    .historial-item { background: #f8f9fa; padding: 0.5rem; margin-bottom: 0.3rem; border-radius: 3px; 
                     font-family: monospace; font-size: 11px; border-left: 3px solid #0b3d91; }
    .historial-item-speci { background: #FFE699; border-left: 3px solid #FFC000; }
    .stButton button { width: 100%; border-radius: 5px; }
    .stButton button[kind="primary"] { background-color: #0b3d91; color: white; }
    .stButton button[kind="primary"]:hover { background-color: #1a4fa0; }
</style>
""", unsafe_allow_html=True)

# ============================================
# FUNCIONES DE GESTIÓN DE ARCHIVOS
# ============================================
def obtener_nombre_archivo_mensual():
    return f"SPJC_METAR_{datetime.now(timezone.utc).strftime('%Y_%m')}.xlsx"

def cargar_registros_mes():
    archivo = DIRECTORIO_DATOS / obtener_nombre_archivo_mensual()
    if archivo.exists():
        try:
            df = pd.read_excel(archivo, sheet_name='METAR SPJC')
            registros = []
            for _, row in df.iterrows():
                r = row.to_dict()
                r['Día'] = str(r.get('DIA', '')).zfill(2)
                r['Hora'] = str(r.get('HORA', '')).zfill(4)
                r['Tipo'] = r.get('TIPO', '')
                r['METAR_Completo'] = r.get('METAR', '')
                registros.append(r)
            return registros
        except:
            return []
    return []

def guardar_registros_mes(registros):
    if not registros: 
        return False, "No hay registros"
    try:
        archivo = DIRECTORIO_DATOS / obtener_nombre_archivo_mensual()
        df = pd.DataFrame(registros)
        
        rename_map = {
            'Día': 'DIA', 'Hora': 'HORA', 'Tipo': 'TIPO',
            'Dirección_Viento': 'DIR VIENTO', 'Intensidad_Viento': 'INTENSIDAD',
            'Variación_Viento': 'VARIACION', 'Visibilidad_Original': 'VIS (ORIGINAL)',
            'Visibilidad_Metros': 'VIS (CODIGO)', 'Visibilidad_Mínima': 'VIS MIN',
            'RVR': 'RVR', 'Fenómeno_Texto': 'FENOMENO', 'Fenómeno_Código': 'WX',
            'Nubes_Texto': 'NUBOSIDAD', 'Nubes_Código': 'CLD',
            'Temperatura': 'TEMP °C', 'Punto_Rocío': 'ROCÍO °C',
            'Humedad_Relativa_%': 'HR %', 'QNH': 'QNH',
            'Presión_Estación': 'PRESION', 'Info_Suplementaria': 'RMK',
            'METAR_Completo': 'METAR'
        }
        df = df.rename(columns=rename_map)
        
        cols = ['DIA','HORA','TIPO','DIR VIENTO','INTENSIDAD','VARIACION',
                'VIS (ORIGINAL)','VIS (CODIGO)','VIS MIN','RVR','FENOMENO','WX',
                'NUBOSIDAD','CLD','TEMP °C','ROCÍO °C','HR %','QNH','PRESION','RMK','METAR']
        df = df[[c for c in cols if c in df.columns]]
        df = df.sort_values(['DIA','HORA'])
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='METAR SPJC', index=False)
        output.seek(0)
        
        with open(archivo, 'wb') as f:
            f.write(output.getvalue())
        return True, f"✅ {len(registros)} registros guardados"
    except Exception as e:
        return False, f"Error: {str(e)}"

# ============================================
# FRAGMENTS - COMPONENTES INTERACTIVOS
# ============================================

@st.fragment
def fragment_fenomenos():
    """Fragment para fenómenos con botón + centrado"""
    st.markdown("**Fenómenos:**")
    
    if 'fenomenos_seleccionados' not in st.session_state:
        st.session_state.fenomenos_seleccionados = []
    
    # Mostrar seleccionados con botón eliminar
    for i, fen in enumerate(st.session_state.fenomenos_seleccionados):
        cols = st.columns([10, 1])
        with cols[0]: 
            st.info(f"📌 {fen}")
        with cols[1]:
            if st.button("✖", key=f"del_fen_{i}"):
                st.session_state.fenomenos_seleccionados.pop(i)
                st.rerun()
    
    # Selector y botón centrado
    col1, col2, col3 = st.columns([4, 2, 4])
    with col2:
        opciones = []
        for cat, fens in FENOMENOS_LIMA.items():
            opciones.append(f"--- {cat} ---")
            opciones.extend(fens)
        
        nuevo = st.selectbox("##", options=[""] + opciones, key="sel_fen",
                            format_func=lambda x: x if x else "Seleccione...",
                            label_visibility="collapsed")
        
        if st.button("➕ Agregar Fenómeno", use_container_width=True):
            if nuevo and not nuevo.startswith("---"):
                if nuevo not in st.session_state.fenomenos_seleccionados:
                    st.session_state.fenomenos_seleccionados.append(nuevo)
                    st.rerun()

@st.fragment
def fragment_nubes():
    """Fragment para nubes con VV y validación 1-3-5"""
    st.markdown("**Nubosidad:**")
    
    if 'capas_nubes' not in st.session_state:
        st.session_state.capas_nubes = []
    if 'vv_activo' not in st.session_state:
        st.session_state.vv_activo = False
        st.session_state.vv_valor = ""
    
    # Mostrar VV si activo
    if st.session_state.vv_activo:
        cols = st.columns([1, 3, 3, 1])
        with cols[0]: 
            st.markdown("**VV**")
        with cols[1]: 
            txt = "DESCONOCIDA" if st.session_state.vv_valor == "///" else f"{st.session_state.vv_valor}m"
            st.markdown(f"📊 {txt}")
        with cols[2]:
            if st.session_state.vv_valor == "///":
                st.markdown("**VV///**")
            else:
                try:
                    cod = f"VV{round(int(st.session_state.vv_valor)/30):03d}"
                    st.markdown(f"**{cod}**")
                except:
                    st.markdown("**VV///**")
        with cols[3]:
            if st.button("✖", key="del_vv"):
                st.session_state.vv_activo = False
                st.session_state.vv_valor = ""
                st.rerun()
        st.markdown("---")
    
    # Mostrar capas existentes
    for i, capa in enumerate(st.session_state.capas_nubes):
        cols = st.columns([1, 1, 1.5, 1.5, 0.5])
        with cols[0]: 
            st.markdown(f"**Capa {i+1}**")
        with cols[1]: 
            st.markdown(f"**{capa['octas']}** oct")
        with cols[2]: 
            st.markdown(f"**{capa['tipo']}**")
        with cols[3]: 
            st.markdown(f"**{capa['altura']}m**")
        with cols[4]:
            if st.button("✖", key=f"del_capa_{i}"):
                st.session_state.capas_nubes.pop(i)
                st.rerun()
    
    st.markdown("---")
    
    if not st.session_state.vv_activo:
        tipo = st.radio("##", ["☁️ Capa", "🌫️ VV"], horizontal=True, key="tipo_nube",
                       label_visibility="collapsed")
        
        if tipo == "☁️ Capa":
            cols = st.columns([1, 1.5, 2, 1])
            with cols[0]: 
                octa = st.selectbox("Oct", [""]+OCTAS, key="nueva_octa")
            with cols[1]: 
                tipo_n = st.selectbox("Tipo", [""]+TIPOS_NUBES, key="nuevo_tipo")
            with cols[2]: 
                alt = st.text_input("Alt (m)", key="nueva_altura", placeholder="300")
            with cols[3]:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("➕", key="add_capa", use_container_width=True):
                    if octa and tipo_n and alt:
                        try:
                            alt_i = int(alt)
                            if 0 <= alt_i <= 30000:
                                err = validar_regla_nubes(st.session_state.capas_nubes, int(octa), tipo_n, alt)
                                if not err:
                                    st.session_state.capas_nubes.append({'octas':octa,'tipo':tipo_n,'altura':alt})
                                    st.rerun()
                                else: 
                                    st.error(err)
                            else: 
                                st.error("Altura fuera de rango")
                        except: 
                            st.error("Número inválido")
        else:  # VV
            cols = st.columns([3, 2, 1])
            with cols[0]: 
                vv_alt = st.text_input("Altura VV (m)", key="vv_alt", placeholder="600 o vacío")
            with cols[1]:
                if vv_alt:
                    try: 
                        st.markdown(f"<br><b>VV{round(int(vv_alt)/30):03d}</b>", unsafe_allow_html=True)
                    except: 
                        st.markdown("<br><b>VV///</b>", unsafe_allow_html=True)
                else: 
                    st.markdown("<br><b>VV///</b>", unsafe_allow_html=True)
            with cols[2]:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("➕ VV", key="add_vv", use_container_width=True):
                    if st.session_state.capas_nubes:
                        st.error("No puede combinar VV con capas de nubes")
                    elif not vv_alt:
                        st.session_state.vv_activo = True
                        st.session_state.vv_valor = "///"
                        st.session_state.capas_nubes = []
                        st.rerun()
                    else:
                        try:
                            vv_i = int(vv_alt)
                            if 0 <= vv_i <= 3000:
                                st.session_state.vv_activo = True
                                st.session_state.vv_valor = str(vv_i)
                                st.session_state.capas_nubes = []
                                st.rerun()
                            else: 
                                st.error("Altura debe ser 0-3000m")
                        except: 
                            st.error("Número inválido")

def validar_regla_nubes(capas, octas, tipo, alt):
    n = len(capas) + 1
    if n > 3: 
        return "❌ Máximo 3 capas permitidas"
    if n == 1 and octas < 1: 
        return "❌ Primera capa: mínimo 1 octa"
    if n == 2 and octas < 3: 
        return "❌ Segunda capa: mínimo 3 octas"
    if n == 3 and octas < 5: 
        return "❌ Tercera capa: mínimo 5 octas"
    for c in capas:
        if c['tipo'] == tipo and c['altura'] == alt:
            return "⚠️ Capa duplicada"
    return None

def convertir_nubes_a_metar():
    if st.session_state.get('vv_activo'):
        if st.session_state.vv_valor == "///": 
            return "VV///"
        try: 
            return f"VV{round(int(st.session_state.vv_valor)/30):03d}"
        except: 
            return "VV///"
    if not st.session_state.get('capas_nubes'): 
        return "NSC"
    codigos = []
    for c in st.session_state.capas_nubes:
        alt = round(int(c['altura'])/30)
        alt = min(max(alt, 1), 999)
        cod = f"{MAPEO_OCTAS[c['octas']]}{alt:03d}"
        if c['tipo'] in ['CB', 'TCU']: 
            cod += c['tipo']
        codigos.append(cod)
    return " ".join(codigos[:4])

# ============================================
# FUNCIONES DE PROCESAMIENTO
# ============================================
def procesar_viento(dir, inten, var):
    d = int(dir)
    i = str(inten).upper().strip()
    if d == 0 and i == "00": 
        return "00000KT"
    
    if 'G' in i:
        parts = i.replace('G', ' ').split()
        base = int(parts[0])
        gust = int(parts[1]) if len(parts) > 1 else base
        im = f"{base:02d}G{gust:02d}"
    else:
        im = f"{int(i):02d}"
    
    if not var: 
        return f"{d:03d}{im}KT"
    
    try:
        if 'V' not in var: 
            return f"{d:03d}{im}KT"
        de, ha = map(int, var.split('V'))
        diff = min(abs(ha - de), 360 - abs(ha - de))
        if diff < 60: 
            return f"{d:03d}{im}KT"
        if diff >= 180 or int(i) < 3: 
            return f"VRB{im}KT"
        return f"{d:03d}{im}KT {de:03d}V{ha:03d}"
    except:
        return f"{d:03d}{im}KT"

def convertir_visibilidad(v):
    v = v.strip().upper()
    if not v: 
        raise ValueError("Visibilidad requerida")
    try:
        if v.endswith("KM"):
            km = float(v[:-2])
            return 9999 if km >= 10 else int(km * 1000)
        if v.endswith("M"):
            return int(v[:-1])
        m = int(v)
        return 9999 if m >= 10000 else m
    except: 
        raise ValueError("Formato inválido")

def procesar_visibilidad_minima(vm, v_m):
    if not vm: 
        return "", ""
    vm = vm.strip().upper()
    for q in [Cuadrante.NW, Cuadrante.NE, Cuadrante.SW, Cuadrante.SE,
              Cuadrante.N, Cuadrante.S, Cuadrante.E, Cuadrante.W]:
        if vm.endswith(q.value):
            val = vm[:-len(q.value)]
            cuad = q
            break
    else: 
        val = vm
        cuad = None
    
    try:
        if val.endswith("KM"):
            mm = 9999 if float(val[:-2]) >= 10 else int(float(val[:-2]) * 1000)
        elif val.endswith("M"):
            mm = int(val[:-1])
        else:
            mm = int(val)
            mm = 9999 if mm >= 10000 else mm
        
        valida = mm < 1500 or (mm < v_m * 0.5 and mm < 5000)
        if not valida: 
            return "", "⚠️ No cumple reglas"
        return (f"{mm:04d}{cuad.value}" if cuad else f"{mm:04d}"), ""
    except: 
        return "", "❌ Formato inválido"

def codificar_fenomenos(texto, vis):
    if not texto: 
        return ""
    texto = texto.lower()
    especiales = []
    
    # Fenómenos especiales
    if "prfg" in texto or "parcial" in texto:
        especiales.append("PRFG")
    if "vcfg" in texto or "vecindad" in texto:
        especiales.append("VCFG")
    if "bcfg" in texto or "bancos" in texto:
        especiales.append("BCFG")
    if "mifg" in texto or "baja" in texto:
        especiales.append("MIFG")
    
    intensidades = {"ligera": "-", "ligero": "-", "moderada": "", "fuerte": "+"}
    descriptores = {"sh": "SH", "ts": "TS", "fz": "FZ"}
    precipitacion = {"lluvia": "RA", "llovizna": "DZ", "nieve": "SN", "granizo": "GR"}
    
    resultados = []
    for p in texto.split(','):
        p = p.strip()
        if not p: 
            continue
        
        cod = None
        for k, v in precipitacion.items():
            if k in p: 
                cod = v
                break
        
        if not cod:
            if "neblina" in p:
                cod = "BR" if vis <= 5000 else None
            elif "niebla" in p and "parcial" not in p and "baja" not in p:
                cod = "FG" if vis < 1000 else None
        
        if cod:
            desc = ""
            intens = ""
            for k, v in descriptores.items():
                if k in p: 
                    desc = v
                    p = p.replace(k, "")
                    break
            for k, v in intensidades.items():
                if k in p: 
                    intens = v
                    break
            resultados.append(intens + desc + cod)
    
    return " ".join((resultados + especiales)[:3])

# ============================================
# FUNCIÓN PRINCIPAL DE GENERACIÓN
# ============================================
def generar_metar(datos):
    try:
        if not datos['dir_viento'] or not datos['int_viento']:
            raise ValueError("Dirección e intensidad del viento son obligatorias")
        if not datos['vis']:
            raise ValueError("Visibilidad es obligatoria")
        if not datos['temp'] or not datos['rocio'] or not datos['qnh']:
            raise ValueError("Temperatura, Rocío y QNH son obligatorios")
        
        hora = datos['hora']
        if len(hora) != 4 or not hora.isdigit():
            raise ValueError("Hora debe ser HHMM (4 dígitos)")
        if int(hora[:2]) > 23 or int(hora[2:]) > 59:
            raise ValueError("Hora inválida")
        
        viento = procesar_viento(datos['dir_viento'], datos['int_viento'], datos['var_viento'])
        vis_m = convertir_visibilidad(datos['vis'])
        
        vis_min = ""
        if datos['vis_min']:
            vis_min, err = procesar_visibilidad_minima(datos['vis_min'], vis_m)
            if err: 
                raise ValueError(err)
        
        rvr = datos['rvr'].strip() if datos['rvr'] else ""
        fenomeno = codificar_fenomenos(datos['fenomeno'], vis_m)
        nubes = datos['nubes'] if datos['nubes'] else "NSC"
        
        temp = float(datos['temp'])
        rocio = float(datos['rocio'])
        qnh = int(float(datos['qnh']))
        
        if rocio > temp:
            raise ValueError("El punto de rocío no puede ser mayor que la temperatura")
        
        temp_metar = redondear_metar(temp)
        rocio_metar = redondear_metar(rocio)
        
        partes = [f"{datos['tipo']} SPJC {datos['dia']}{hora}Z {viento}"]
        
        if nubes == "CAVOK":
            partes.append("CAVOK")
        else:
            partes.append(f"{vis_m:04d}")
            if vis_min: 
                partes.append(vis_min)
            if rvr: 
                partes.append(rvr)
            if fenomeno: 
                partes.append(fenomeno)
            partes.append(nubes)
        
        partes.append(f"{temp_metar:02d}/{rocio_metar:02d} Q{qnh}")
        if datos['suplementaria']:
            partes.append(datos['suplementaria'].upper())
        
        metar = " ".join(partes) + "="
        
        hr_calc = calcular_hr_automatica(temp, rocio)
        
        registro = {
            'Día': str(datos['dia']).zfill(2),
            'Hora': hora,
            'Tipo': datos['tipo'],
            'Dirección_Viento': datos['dir_viento'],
            'Intensidad_Viento': datos['int_viento'],
            'Variación_Viento': datos['var_viento'],
            'Visibilidad_Original': datos['vis'],
            'Visibilidad_Metros': vis_m,
            'Visibilidad_Mínima': vis_min,
            'RVR': rvr,
            'Fenómeno_Texto': datos['fenomeno'],
            'Fenómeno_Código': fenomeno,
            'Nubes_Texto': datos['nubes'],
            'Nubes_Código': nubes,
            'Temperatura': temp,
            'Punto_Rocío': rocio,
            'Humedad_Relativa_%': hr_calc if hr_calc else "",
            'QNH': qnh,
            'Presión_Estación': datos['presion'],
            'Info_Suplementaria': datos['suplementaria'],
            'METAR_Completo': metar
        }
        
        return {'success': True, 'metar': metar, 'registro': registro}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

# ============================================
# FUNCIÓN TN/TX SIMPLIFICADA
# ============================================
def mostrar_tn_tx():
    hora = datetime.now(timezone.utc).strftime("%H%M")
    h = int(hora)
    
    if 1200 <= h < 1300:
        st.markdown("### 📉 TN (Temperatura Mínima) - 12Z")
        val = st.text_input("Valor TN (°C)", key="tn_valor", placeholder="Ej: 18.5")
        if val:
            try:
                float(val)
                st.session_state.tn_tx = f"TN{val}/1200Z"
                st.success(f"✅ TN{val}/1200Z")
            except:
                st.error("Valor inválido")
                st.session_state.tn_tx = None
        else:
            st.session_state.tn_tx = None
        return True
    elif 2200 <= h < 2300:
        st.markdown("### 📈 TX (Temperatura Máxima) - 22Z")
        val = st.text_input("Valor TX (°C)", key="tx_valor", placeholder="Ej: 25.5")
        if val:
            try:
                float(val)
                st.session_state.tn_tx = f"TX{val}/2200Z"
                st.success(f"✅ TX{val}/2200Z")
            except:
                st.error("Valor inválido")
                st.session_state.tn_tx = None
        else:
            st.session_state.tn_tx = None
        return True
    return False

# ============================================
# FUNCIÓN PARA ACTUALIZAR REGISTRO
# ============================================
def actualizar_o_insertar_registro(registros, nuevo_registro):
    dia_nuevo = str(nuevo_registro.get('Día', '')).zfill(2)
    hora_nueva = str(nuevo_registro.get('Hora', '')).zfill(4)
    clave = f"{dia_nuevo}_{hora_nueva}"
    
    for i, reg in enumerate(registros):
        dia_existente = str(reg.get('Día', '')).zfill(2)
        hora_existente = str(reg.get('Hora', '')).zfill(4)
        if f"{dia_existente}_{hora_existente}" == clave:
            registros[i] = nuevo_registro
            guardar_registros_mes(registros)
            return "actualizado"
    
    registros.insert(0, nuevo_registro)
    guardar_registros_mes(registros)
    return "insertado"

# ============================================
# FUNCIÓN PARA EXPORTAR EXCEL
# ============================================
def exportar_a_excel(registros):
    if not registros:
        return None, "No hay registros"
    
    try:
        datos = []
        for r in registros:
            datos.append({
                'DIA': str(r.get('Día', '')).zfill(2),
                'HORA': str(r.get('Hora', '')).zfill(4),
                'TIPO': r.get('Tipo', ''),
                'DIR VIENTO': r.get('Dirección_Viento', ''),
                'INTENSIDAD': r.get('Intensidad_Viento', ''),
                'VARIACION': r.get('Variación_Viento', ''),
                'VIS (ORIGINAL)': r.get('Visibilidad_Original', ''),
                'VIS (CODIGO)': r.get('Visibilidad_Metros', ''),
                'VIS MIN': r.get('Visibilidad_Mínima', ''),
                'RVR': r.get('RVR', ''),
                'FENOMENO': r.get('Fenómeno_Texto', ''),
                'WX': r.get('Fenómeno_Código', ''),
                'NUBOSIDAD': r.get('Nubes_Texto', ''),
                'CLD': r.get('Nubes_Código', ''),
                'TEMP °C': r.get('Temperatura', ''),
                'ROCÍO °C': r.get('Punto_Rocío', ''),
                'HR %': r.get('Humedad_Relativa_%', ''),
                'QNH': r.get('QNH', ''),
                'PRESION': r.get('Presión_Estación', ''),
                'RMK': r.get('Info_Suplementaria', ''),
                'METAR': r.get('METAR_Completo', '')
            })
        
        df = pd.DataFrame(datos)
        df = df.sort_values(['DIA', 'HORA'])
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='METAR SPJC', index=False)
        output.seek(0)
        
        return output, f"✅ {len(registros)} registros exportados"
    except Exception as e:
        return None, f"Error: {str(e)}"

# ============================================
# LIMPIAR CAMPOS
# ============================================
def limpiar_campos():
    campos = ['dir_viento', 'int_viento', 'var_desde', 'var_hasta', 'vis', 'vis_min', 'rvr',
              'temp', 'rocio', 'qnh', 'presion', 'suplementaria', 'pp_select', 'tn_valor', 'tx_valor']
    for c in campos:
        if c in st.session_state:
            st.session_state[c] = ""
    st.session_state.fenomenos_seleccionados = []
    st.session_state.capas_nubes = []
    st.session_state.vv_activo = False
    st.session_state.vv_valor = ""
    st.session_state.dia = datetime.now(timezone.utc).strftime("%d")
    st.session_state.hora = datetime.now(timezone.utc).strftime("%H%M")
    st.rerun()

# ============================================
# INICIALIZACIÓN DE SESIÓN
# ============================================
if 'registros' not in st.session_state:
    st.session_state.registros = cargar_registros_mes()
if 'historial' not in st.session_state:
    st.session_state.historial = []
if 'contador' not in st.session_state:
    st.session_state.contador = len(st.session_state.registros)
if 'tipo' not in st.session_state:
    st.session_state.tipo = TipoReporte.METAR.value
if 'dia' not in st.session_state:
    st.session_state.dia = datetime.now(timezone.utc).strftime("%d")
if 'hora' not in st.session_state:
    st.session_state.hora = datetime.now(timezone.utc).strftime("%H%M")

# ============================================
# SIDEBAR - TABLAS DE REFERENCIA
# ============================================
with st.sidebar:
    st.markdown("### 📋 REFERENCIAS RÁPIDAS")
    
    with st.expander("🌧️ Precipitación (PPTRZ)"):
        for k, v in OPCIONES_PP.items():
            st.markdown(f"**{k}**: {v}")
    
    with st.expander("🌡️ TN/TX"):
        st.markdown("**TN**: 12Z (Temperatura Mínima)")
        st.markdown("**TX**: 22Z (Temperatura Máxima)")
    
    with st.expander("🌫️ Visibilidad Mínima"):
        st.markdown("**Ejemplos:** 0800SW, 1200NE, 1500N")
    
    with st.expander("🌀 RVR"):
        st.markdown("**R32/0400** - Pista 32, 400m")
        st.markdown("**R12R/M0050** - Pista 12R, < 50m")
        st.markdown("**R14L/P2000** - Pista 14L, > 2000m")
    
    with st.expander("☁️ Códigos de Nubes"):
        st.markdown("**FEW**: 1-2 octas")
        st.markdown("**SCT**: 3-4 octas")
        st.markdown("**BKN**: 5-7 octas")
        st.markdown("**OVC**: 8 octas")
        st.markdown("**VV**: Visibilidad Vertical")

# ============================================
# HEADER PRINCIPAL
# ============================================
col1, col2 = st.columns([3, 1])
with col1:
    st.markdown("<h2 style='color:#0b3d91;'>REGISTRO METAR/SPECI SPJC</h2>", unsafe_allow_html=True)
    st.markdown("Aeropuerto Internacional Jorge Chávez - CORPAC Perú")
with col2:
    st.markdown(f"<div style='text-align:right;'>{datetime.now(timezone.utc).strftime('%d/%m/%Y')}<br><b>{obtener_nombre_archivo_mensual()}</b></div>", unsafe_allow_html=True)

st.markdown("---")

# ============================================
# INTERFAZ PRINCIPAL
# ============================================
col_izq, col_der = st.columns([2, 1])

with col_izq:
    # TIPO DE REPORTE
    st.markdown("<div class='section-title'>TIPO DE REPORTE</div>", unsafe_allow_html=True)
    st.selectbox("##", [t.value for t in TipoReporte], key='tipo_selector',
                 on_change=lambda: st.session_state.__setitem__('tipo', st.session_state.tipo_selector),
                 label_visibility="collapsed")
    
    # DÍA Y HORA
    st.markdown("<div class='section-title'>FECHA Y HORA (UTC)</div>", unsafe_allow_html=True)
    cc = st.columns(2)
    with cc[0]:
        st.text_input("Día", key='dia', placeholder="01-31")
    with cc[1]:
        st.text_input("Hora", key='hora', placeholder="HHMM")
    
    # VIENTO
    st.markdown("<div class='section-title'>VIENTO</div>", unsafe_allow_html=True)
    cc = st.columns([2, 2, 1, 2, 2])
    with cc[0]:
        st.text_input("Dirección", key='dir_viento', placeholder="360")
    with cc[1]:
        st.text_input("Intensidad", key='int_viento', placeholder="15")
    with cc[2]:
        st.markdown("<br><b>-</b>", unsafe_allow_html=True)
    with cc[3]:
        st.text_input("Desde", key='var_desde', placeholder="340")
    with cc[4]:
        st.text_input("Hasta", key='var_hasta', placeholder="080")
    
    var_viento = f"{st.session_state.get('var_desde','')}V{st.session_state.get('var_hasta','')}" if st.session_state.get('var_desde') and st.session_state.get('var_hasta') else ""
    
    # VISIBILIDAD
    st.markdown("<div class='section-title'>VISIBILIDAD</div>", unsafe_allow_html=True)
    cc = st.columns(3)
    with cc[0]:
        st.text_input("Visibilidad", key='vis', placeholder="10km, 5000m, 9999")
    with cc[1]:
        st.text_input("Visibilidad Mínima", key='vis_min', placeholder="1200SW")
    with cc[2]:
        st.text_input("RVR", key='rvr', placeholder="R32/0400")
    
    # FENÓMENOS
    st.markdown("<div class='section-title'>FENÓMENOS</div>", unsafe_allow_html=True)
    fragment_fenomenos()
    fenomeno = " ".join([f.split(" - ")[0] for f in st.session_state.get('fenomenos_seleccionados', [])])
    
    # NUBES
    st.markdown("<div class='section-title'>NUBOSIDAD</div>", unsafe_allow_html=True)
    fragment_nubes()
    nubes = convertir_nubes_a_metar()
    
    # TEMPERATURA Y PRESIÓN
    st.markdown("<div class='section-title'>TEMPERATURA Y PRESIÓN</div>", unsafe_allow_html=True)
    cc = st.columns(4)
    with cc[0]:
        st.text_input("Temperatura °C", key='temp', placeholder="-10 a 40")
    with cc[1]:
        st.text_input("Punto de Rocío °C", key='rocio', placeholder="≤ Temp")
    with cc[2]:
        st.text_input("QNH hPa", key='qnh', placeholder="850-1100")
    with cc[3]:
        st.text_input("Presión Estación", key='presion', placeholder="Opcional")
    
    if st.session_state.temp and st.session_state.rocio:
        try:
            hr = calcular_hr_automatica(float(st.session_state.temp), float(st.session_state.rocio))
            if hr:
                st.caption(f"💧 HR calculada: {hr}%")
        except:
            pass
    
    # INFORMACIÓN SUPLEMENTARIA
    st.markdown("<div class='section-title'>INFORMACIÓN SUPLEMENTARIA</div>", unsafe_allow_html=True)
    st.text_input("##", key='suplementaria', placeholder="NOSIG, RMK CB AL NE, etc.", label_visibility="collapsed")
    
    # TN/TX (solo si corresponde la hora)
    tn_tx_activo = mostrar_tn_tx()
    
    # PRECIPITACIÓN (siempre al final)
    st.markdown("<div class='section-title'>PRECIPITACIÓN</div>", unsafe_allow_html=True)
    pp_valor = st.selectbox("##", options=list(OPCIONES_PP.keys()), key="pp_select",
                           format_func=lambda x: f"{x} - {OPCIONES_PP[x]}", label_visibility="collapsed")
    
    # BOTONES
    st.markdown("---")
    cc = st.columns(2)
    with cc[0]:
        generar = st.button("GENERAR METAR", use_container_width=True, type="primary")
    with cc[1]:
        limpiar = st.button("LIMPIAR CAMPOS", use_container_width=True)
    
    if limpiar:
        limpiar_campos()
    
    if generar:
        errores = []
        if not pp_valor:
            errores.append("Seleccione precipitación")
        if tn_tx_activo and not st.session_state.get('tn_tx'):
            errores.append("Complete TN/TX")
        
        if errores:
            for e in errores:
                st.error(f"❌ {e}")
        else:
            rmk = st.session_state.suplementaria
            if pp_valor:
                rmk = f"{pp_valor} {rmk}".strip()
            if tn_tx_activo and st.session_state.get('tn_tx'):
                rmk = f"{st.session_state.tn_tx} {rmk}".strip()
            
            datos = {
                'tipo': st.session_state.tipo,
                'dia': st.session_state.dia,
                'hora': st.session_state.hora,
                'dir_viento': st.session_state.dir_viento,
                'int_viento': st.session_state.int_viento,
                'var_viento': var_viento,
                'vis': st.session_state.vis,
                'vis_min': st.session_state.vis_min,
                'rvr': st.session_state.rvr,
                'fenomeno': fenomeno,
                'nubes': nubes,
                'temp': st.session_state.temp,
                'rocio': st.session_state.rocio,
                'qnh': st.session_state.qnh,
                'presion': st.session_state.presion,
                'suplementaria': rmk
            }
            
            resultado = generar_metar(datos)
            
            if resultado['success']:
                accion = actualizar_o_insertar_registro(st.session_state.registros, resultado['registro'])
                st.session_state.historial.insert(0, resultado['metar'])
                st.session_state.historial = st.session_state.historial[:20]
                st.session_state.contador = len(st.session_state.registros)
                st.session_state.ultimo_metar = resultado['metar']
                
                if accion == "actualizado":
                    st.warning(f"🔄 Reporte de las {resultado['registro']['Hora']}Z ACTUALIZADO")
                else:
                    st.success(f"✅ Reporte de las {resultado['registro']['Hora']}Z AGREGADO")
                st.rerun()
            else:
                st.error(f"❌ {resultado['error']}")

with col_der:
    # ÚLTIMO REPORTE
    st.markdown("<div class='section-title'>📋 ÚLTIMO REPORTE</div>", unsafe_allow_html=True)
    if 'ultimo_metar' in st.session_state:
        st.markdown(f"<div class='metar-box'>{st.session_state.ultimo_metar}</div>", unsafe_allow_html=True)
    else:
        st.info("---")
    
    # ESTADÍSTICAS
    st.markdown("---")
    st.markdown("<div class='section-title'>📊 ESTADÍSTICAS</div>", unsafe_allow_html=True)
    st.metric("REGISTROS EN MEMORIA", st.session_state.contador)
    
    # EXPORTAR
    if st.button("📥 EXPORTAR EXCEL", use_container_width=True):
        if st.session_state.registros:
            archivo, mensaje = exportar_a_excel(st.session_state.registros)
            if archivo:
                st.download_button(
                    label="✅ DESCARGAR ARCHIVO",
                    data=archivo,
                    file_name=obtener_nombre_archivo_mensual(),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                st.success(mensaje)
            else:
                st.warning(mensaje)
        else:
            st.warning("No hay registros para exportar")
    
    # LIMPIAR MEMORIA
    if st.button("🗑️ LIMPIAR MEMORIA", use_container_width=True):
        st.session_state.registros = []
        st.session_state.historial = []
        st.session_state.contador = 0
        if 'ultimo_metar' in st.session_state:
            del st.session_state.ultimo_metar
        st.success("Memoria limpiada")
        st.rerun()
    
    # HISTORIAL
    st.markdown("---")
    st.markdown("<div class='section-title'>📜 HISTORIAL</div>", unsafe_allow_html=True)
    if st.session_state.historial:
        for metar in st.session_state.historial[:8]:
            clase = "historial-item-speci" if "SPECI" in metar else "historial-item"
            st.markdown(f"<div class='{clase}'>{metar}</div>", unsafe_allow_html=True)
    else:
        st.info("No hay METARs en el historial")

# ============================================
# FOOTER
# ============================================
st.markdown("---")
st.markdown("""
<div style='text-align:center; color:#666; padding:10px; font-size:0.8rem;'>
    METAR Digital v17.0 - CORPAC Perú - Aeropuerto Internacional Jorge Chávez (SPJC)
</div>
""", unsafe_allow_html=True)