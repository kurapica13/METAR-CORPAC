# METAR Digital SPJC — Versión Flask
## Guía completa de instalación y uso

---

## ¿Qué es Flask y cómo funciona?

Flask es un mini-servidor web que corre en tu computadora.
Cuando ejecutas el programa, Flask abre un "servidor local" en el
puerto 5000, y tú accedes a la aplicación desde cualquier navegador
escribiendo:  http://localhost:5000

No necesitas internet. Todo corre en tu máquina.

---

## ESTRUCTURA DE ARCHIVOS

```
metar_flask/
│
├── app.py                  ← El programa principal (Flask)
├── requirements.txt        ← Lista de librerías necesarias
├── README.md               ← Esta guía
│
├── templates/              ← Las páginas HTML
│   ├── login.html          ← Pantalla de login
│   └── index.html          ← Pantalla principal del formulario
│
└── datos_metar/            ← Aquí se guardan los Excel (se crea solo)
    └── SPJC_METAR_2025_01.xlsx   (ejemplo)
```

---

## INSTALACIÓN (solo la primera vez)

### Paso 1 — Instalar Python
Si no tienes Python instalado, descárgalo desde:
https://www.python.org/downloads/
Versión recomendada: 3.10 o superior.
Durante la instalación marca la casilla "Add Python to PATH".

### Paso 2 — Abrir una terminal
- Windows: Busca "cmd" o "PowerShell" en el menú inicio
- Mac/Linux: Abre la aplicación "Terminal"

### Paso 3 — Ir a la carpeta del proyecto
```
cd ruta/a/metar_flask
```
Por ejemplo:
```
cd C:\Users\TuNombre\Desktop\metar_flask
```

### Paso 4 — Instalar las librerías necesarias
```
pip install flask pandas openpyxl
```
Espera a que termine (puede tardar 1-2 minutos la primera vez).

---

## CÓMO EJECUTAR EL PROGRAMA

### Cada vez que quieras usar la aplicación:

1. Abre una terminal
2. Ve a la carpeta del proyecto:
   ```
   cd ruta/a/metar_flask
   ```
3. Ejecuta:
   ```
   python app.py
   ```
4. Verás algo como:
   ```
    * Running on http://127.0.0.1:5000
    * Press CTRL+C to quit
   ```
5. Abre tu navegador y escribe:
   ```
   http://localhost:5000
   ```
6. ¡Listo! Aparece el login.

### Para detener el programa:
Presiona CTRL+C en la terminal.

---

## USUARIOS Y CONTRASEÑAS

Por defecto hay dos usuarios configurados en app.py:

| Usuario | Contraseña  |
|---------|-------------|
| admin   | corpac2024  |
| metar   | spjc2024    |

### Cómo cambiar las contraseñas:
Abre app.py con cualquier editor de texto (Notepad, VS Code, etc.)
Busca esta sección (cerca del inicio del archivo):

```python
USUARIOS = {
    "admin":  "corpac2024",
    "metar":  "spjc2024",
}
```

Cambia los valores entre comillas por las contraseñas que quieras.
Guarda el archivo y reinicia el programa.

### Cómo agregar más usuarios:
```python
USUARIOS = {
    "admin":     "corpac2024",
    "metar":     "spjc2024",
    "operador1": "miPassword123",   ← nuevo usuario
}
```

---

## USO DE LA APLICACIÓN

### Pantalla principal — Formulario METAR

El formulario está dividido en secciones:

**DATOS DEL REPORTE**
- Tipo: METAR o SPECI
- Día: número del día (01-31)
- Hora UTC: formato HHMM (ej: 1230 para 12:30 UTC)

**VIENTO**
- Dirección: en grados (000-360)
- Intensidad: en nudos. Para ráfagas escribe: 15G25
- Variación: solo si varía ≥60°, formato 340V080

**VISIBILIDAD**
- Puedes escribir: 10km, 5000m, 9999, 1500
- Vis. Mínima: solo si hay diferencia por sectores (ej: 1200SW)
- RVR: si aplica, formato R32/0400

**FENÓMENOS** (sección separada debajo del formulario)
- Selecciona del desplegable y haz clic en ➕ Agregar
- Máximo 3 fenómenos
- Para eliminar, haz clic en ✕

**NUBOSIDAD** (sección separada)
- Selecciona octas, tipo de nube y altura en metros
- Haz clic en ➕ Agregar capa
- Máximo 4 capas

**TEMPERATURA Y PRESIÓN**
- Temp y Rocío en °C
- HR en % (opcional)
- QNH en hPa

**INFO SUPLEMENTARIA**
- Siempre debe incluir PPxxx (precipitación)
- A las 12Z agrega: TN seguido del valor (ej: TN12/)
- A las 22Z agrega: TX seguido del valor (ej: TX28/)
- Ejemplo: PP000 NOSIG
- Ejemplo 12Z: PP000 TN12/ NOSIG

### Generar el METAR
Haz clic en "✅ GENERAR METAR / SPECI"
- Si hay errores, aparece un mensaje rojo explicando qué falta
- Si es correcto, aparece el METAR en la columna derecha
- El formulario se limpia automáticamente para el siguiente reporte

### Exportar a Excel
Haz clic en "📥 Descargar Excel del mes"
El archivo se descarga con el nombre: SPJC_METAR_2025_01.xlsx

---

## DIFERENCIAS CON STREAMLIT

| Característica      | Streamlit                | Flask                    |
|---------------------|--------------------------|--------------------------|
| Instalación         | pip install streamlit    | pip install flask        |
| Ejecutar            | streamlit run app.py     | python app.py            |
| Puerto              | localhost:8501           | localhost:5000           |
| Login               | Problemático con CSS     | HTML nativo, sin problemas|
| Diseño              | Limitado por Streamlit   | 100% control con HTML/CSS|
| Rendimiento         | Recarga toda la página   | Solo recarga lo necesario|
| Complejidad código  | Menos código             | Un poco más de código    |

---

## SOLUCIÓN DE PROBLEMAS COMUNES

**Error: "flask not found" o "No module named flask"**
Solución: Ejecuta: pip install flask pandas openpyxl

**Error: "Port 5000 already in use"**
Solución: Cambia el puerto en la última línea de app.py:
```python
app.run(debug=True, port=5001)  # usa otro número
```
Y accede a: http://localhost:5001

**La sesión se cierra sola**
El navegador guarda la sesión. Si reinicias el programa, tendrás
que volver a iniciar sesión (comportamiento normal).

**Los datos del Excel no aparecen al reiniciar**
Los datos se cargan automáticamente desde el archivo Excel mensual
que está en la carpeta datos_metar/. Si borras esa carpeta, se
pierden los registros.

---

## DESPLIEGUE EN INTERNET (opcional)

Si quieres que otras personas accedan desde fuera de tu computadora:

### Opción gratuita — Render.com
1. Crea cuenta en https://render.com
2. Sube el código a GitHub
3. En Render, crea un "Web Service" apuntando a tu repositorio
4. Comando de inicio: python app.py

### Opción gratuita — Railway.app
1. Crea cuenta en https://railway.app
2. Conecta tu repositorio de GitHub
3. Railway detecta Flask automáticamente

Para producción, cambia la última línea de app.py a:
```python
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
```

---

## PERSONALIZACIÓN

### Cambiar el nombre del aeropuerto
Busca "SPJC" en app.py y en los templates HTML y reemplázalo.

### Agregar más usuarios
Ver sección "USUARIOS Y CONTRASEÑAS" arriba.

### Cambiar el diseño visual
Edita el archivo templates/index.html
El CSS está en la sección <style> al inicio del archivo.
No necesitas saber HTML avanzado — los colores y tamaños
están claramente comentados.

---

Desarrollado para CORPAC Perú — Aeropuerto Internacional Jorge Chávez
