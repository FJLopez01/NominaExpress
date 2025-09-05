# 💼 Sistema de Nóminas Automático

Sistema automatizado para el procesamiento y envío de recibos de nómina por correo electrónico, desarrollado en Python con interfaz web usando Streamlit.

## 📋 Características

- ✅ **Procesamiento automático** de archivos XML (CFDI)
- 📄 **Vinculación automática** con PDFs por CURP
- 📧 **Envío masivo** de correos electrónicos
- 🖥️ **Interfaz web intuitiva** con Streamlit
- 📊 **Monitoreo en tiempo real** del procesamiento
- 📈 **Reportes y estadísticas** detalladas
- 🔍 **Validación de datos** y manejo de errores

## 🚀 Demo

![Sistema de Nóminas](https://img.shields.io/badge/Status-Production%20Ready-green)
![Python](https://img.shields.io/badge/Python-3.8+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red)

### Vista previa de la interfaz:
- **Panel de control** con métricas en tiempo real
- <img width="1915" height="896" alt="image" src="https://github.com/user-attachments/assets/4fb04015-d9fe-4c4f-a795-a89b6ae0fb75" />

- **Validación automática** de archivos y configuración
- <img width="1918" height="894" alt="image" src="https://github.com/user-attachments/assets/848fff14-3f49-4a51-8a3d-a29824d4f808" />

- **Procesamiento con barra de progreso** y logs en vivo
- <img width="1919" height="895" alt="image" src="https://github.com/user-attachments/assets/9e31e2d6-80e6-4a8b-a634-71ac47103555" />

- **Reportes visuales** de resultados
- <img width="1919" height="898" alt="image" src="https://github.com/user-attachments/assets/be5af7fa-a6eb-4202-94f7-dabb948957b9" />


## 📁 Estructura del Proyecto

```
nominas-express/
├── app.py                          # 🖥️ Interfaz web Streamlit
├── config.py                       # ⚙️ Configuración global
├── correo.py                       # 📧 Módulo de envío de emails
├── main.py                         # 🚀 Script principal (modo CLI)
├── procesador.py                   # 🔄 Lógica de procesamiento
├── utilidades.py                   # 🛠️ Funciones auxiliares
├── requirements.txt                # 📦 Dependencias
├── XML/                           # 📄 Archivos XML (CFDI)
├── PDFs/                          # 📁 Archivos PDF (recibos)
└── correos_colaboradores.xlsx     # 📊 Base de datos de correos
```

## 🛠️ Instalación

### Prerequisitos
- Python 3.8 o superior
- Cuenta de Gmail con verificación en 2 pasos
- Contraseña de aplicación de Gmail

### 1. Clonar el repositorio
```bash
git clone https://github.com/tu-usuario/nominas-express.git
cd nominas-express
```

### 2. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 3. Configurar rutas y credenciales
Edita `config.py` con tus rutas y credenciales:

```python
# Rutas de archivos
BASE_PATH = r"C:\Tu\Ruta\Nominas"
XML_PATH = os.path.join(BASE_PATH, "XML")
PDF_PATH = os.path.join(BASE_PATH, "PDFs")
EXCEL_CORREOS = os.path.join(BASE_PATH, "correos_colaboradores.xlsx")

# Configuración de Gmail
EMAIL_SENDER = "tu-email@gmail.com"
EMAIL_PASSWORD = "tu-contraseña-de-aplicacion"  # ⚠️ Usar contraseña de aplicación
```

### 4. Preparar archivos de datos

#### Archivo Excel de correos (`correos_colaboradores.xlsx`):
| Nombre | Correo |
|--------|--------|
| JUAN PEREZ GARCIA | juan.perez@empresa.com |
| MARIA LOPEZ SANCHEZ | maria.lopez@empresa.com |

## 🚀 Uso

### Interfaz Web (Recomendado)
```bash
streamlit run app.py
```
Accede a: `http://localhost:8501`

### Modo Línea de Comandos
```bash
python main.py
```

## 📧 Configuración de Gmail

Para usar Gmail como servidor SMTP:

1. **Activar verificación en 2 pasos** en tu cuenta Google
2. **Generar contraseña de aplicación**:
   - Ve a: [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
   - Selecciona "Correo" y tu dispositivo
   - Copia la contraseña de 16 caracteres

3. **Usar la contraseña de aplicación** en `config.py`

### Variables de Entorno (Más Seguro)
```bash
# Windows
set GMAIL_APP_PASSWORD=tu-contraseña-de-aplicacion
streamlit run app.py

# Linux/Mac
export GMAIL_APP_PASSWORD=tu-contraseña-de-aplicacion
streamlit run app.py
```

## 🔧 Funcionalidades

### Procesamiento Automático
- **Extrae datos** de archivos XML (CFDI) usando namespaces SAT
- **Busca PDFs** correspondientes por CURP
- **Renombra archivos** con formato estandarizado
- **Envía correos** con archivos adjuntos

### Interfaz Web
- **Dashboard** con métricas del sistema
- **Vista previa** de base de correos
- **Procesamiento en tiempo real** con progress bar
- **Logs detallados** de cada operación
- **Reportes visuales** de resultados

### Validaciones
- ✅ Verificación de archivos y directorios
- ✅ Validación de formato XML (CFDI)
- ✅ Búsqueda de CURP en PDFs
- ✅ Validación de direcciones de correo
- ✅ Manejo de errores detallado

## 📊 Ejemplo de Uso

### 1. Colocar archivos
```
XML/
├── nomina_empleado1.xml
├── nomina_empleado2.xml
└── nomina_empleado3.xml

PDFs/
├── recibo_001.pdf
├── recibo_002.pdf  
└── recibo_003.pdf
```

### 2. Ejecutar procesamiento
La aplicación automáticamente:
- Lee los XMLs y extrae nombre + CURP
- Busca el PDF correspondiente por CURP
- Renombra: `JUANPEREZGARCIA-ABCD123456HDFGHI01.pdf`
- Envía correo con XML y PDF adjuntos

### 3. Resultado
```
✅ Correo enviado a juan.perez@empresa.com
✅ Correo enviado a maria.lopez@empresa.com
⚠️ PDF no encontrado para CARLOS MARTINEZ
📊 Resumen: 2 exitosos, 1 error de 3 total
```

## 🤝 Contribuir

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit tus cambios (`git commit -am 'Agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crea un Pull Request

## 📝 Licencia

Este proyecto está bajo la Licencia MIT - mira el archivo [LICENSE](LICENSE) para detalles.

## ⚠️ Consideraciones de Seguridad

- **NUNCA** subas credenciales de correo al repositorio
- Usa **variables de entorno** para datos sensibles
- Considera usar **OAuth2** en lugar de contraseñas de aplicación para producción
- Valida y sanitiza todos los **inputs de usuario**

## 🐛 Resolución de Problemas

### Error: "Application-specific password required"
- Configurar contraseña de aplicación de Gmail según las instrucciones

### Error: "PDF no encontrado"
- Verificar que el CURP en XML coincida con el contenido del PDF
- Revisar que los PDFs sean legibles (no escaneados como imagen)

### Error: "Correo no encontrado"  
- Verificar formato del archivo Excel de correos
- Asegurar que los nombres coincidan (sin tildes, mayúsculas)

## 📞 Soporte

Si encuentras algún problema o tienes sugerencias:
- Crea un [Issue](https://github.com/tu-usuario/nominas-express/issues)
- Contacto: [tu-email@empresa.com](mailto:tu-email@empresa.com)

---

⭐ **¡Si este proyecto te ayudó, dale una estrella!** ⭐


