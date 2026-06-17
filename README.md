# 💼 Sistema de Envío de Nominas

Sistema automatizado para el procesamiento y envío de recibos de nómina por correo electrónico. Lee archivos XML (CFDI 4.0 del SAT), los vincula con sus PDFs correspondientes por CURP, y envía ambos archivos al correo de cada empleado usando Microsoft 365.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red)
![M365](https://img.shields.io/badge/Email-Microsoft_365-0078D4)
![Tests](https://img.shields.io/badge/Tests-pytest-green)

---

## Características

- Procesamiento automático de CFDI 4.0 (XML del SAT)
- Vinculación XML ↔ PDF por CURP mediante índice O(n)
- **Idempotencia por UUID**: si el script se interrumpe y se vuelve a ejecutar, no reenvía correos ya enviados
- Historial persistente en SQLite con todos los envíos
- Envío por Microsoft Graph API (OAuth2) — sin contraseñas que expiren
- Cuerpo del correo editable sin tocar código (`templates/plantilla_correo.txt`)
- Interfaz web con progreso en tiempo real y pestaña de historial
- Logs persistentes por día (`logs/nominas_YYYYMMDD.log`)
- Manejo de errores diferenciado con mensajes claros

---

## Estructura del proyecto

```
nominas-express/
├── src/
│   ├── app.py            # Interfaz web Streamlit (uso diario)
│   ├── main.py           # Modo CLI (automatización / tareas programadas)
│   ├── config.py         # Variables de entorno y rutas
│   ├── procesador.py     # Lógica de negocio principal
│   ├── correo.py         # Envío de emails (Microsoft Graph API)
│   ├── database.py       # Historial de envíos (SQLite)
│   ├── logger.py         # Logging persistente a archivo
│   └── utilidades.py     # Normalización de nombres
├── tests/                # Suite de tests automatizados
├── templates/
│   └── plantilla_correo.txt   # Cuerpo del correo (editable)
├── docs/
│   └── configurar_azure_ad.md # Guía de configuración de Microsoft 365
├── logs/                 # Generado automáticamente al ejecutar
├── .env.example          # Plantilla de configuración (copiar a .env)
├── .gitignore
├── pytest.ini
└── requirements.txt
```

Los archivos de trabajo van **fuera del repositorio**, en la PC donde corre el sistema:

```
C:\Nominas\AGDLegal\          ← BASE_PATH en .env
├── XML\                      # Archivos XML del SAT
├── PDFs\                     # Recibos en PDF
├── correos_colaboradores.xlsx
└── nominas.db                # Base de datos (se crea automáticamente)
```

---

## Instalación

### Prerequisitos

- Python 3.10 o superior ([descargar](https://www.python.org/downloads/))
- Acceso de administrador a Microsoft 365 / Azure AD
- Git ([descargar](https://git-scm.com/))

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/nominas-express.git
cd nominas-express
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python -m venv .venv

# Windows:
.venv\Scripts\activate

# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Preparar los datos

Crea la carpeta de trabajo y agrega los archivos necesarios:

```
C:\Nominas\AGDLegal\
├── XML\
│   ├── nomina_empleado1.xml
│   └── nomina_empleado2.xml
├── PDFs\
│   ├── recibo_001.pdf
│   └── recibo_002.pdf
└── correos_colaboradores.xlsx
```

El archivo Excel debe tener exactamente estas dos columnas (el sistema acepta cualquier capitalización: "nombre", "NOMBRE", "Nombre"):

| Nombre | Correo |
|--------|--------|
| JUAN PEREZ GARCIA | juan.perez@empresa.com |
| MARIA LOPEZ SANCHEZ | maria.lopez@empresa.com |

> Los nombres deben coincidir con los del XML. El sistema normaliza tildes y mayúsculas automáticamente.

### 4. Configurar Microsoft 365

Sigue la guía paso a paso en [`docs/configurar_azure_ad.md`](docs/configurar_azure_ad.md).

Necesitarás acceso al portal de Azure AD como administrador. El proceso toma aproximadamente 15-20 minutos y solo se hace una vez.

### 5. Configurar el archivo .env

```bash
cp .env.example .env
```

Edita `.env` con los valores obtenidos en el paso anterior:

```env
BASE_PATH=C:\Nominas\AGDLegal

AZURE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_SECRET=tu-secreto-de-cliente
EMAIL_SENDER=nominas@agdlegal.com
```

> ⚠️ **Nunca subas `.env` al repositorio.** Ya está incluido en `.gitignore`.

---

## Uso

### Interfaz web — uso diario recomendado

```bash
streamlit run src/app.py
```

Abre el navegador en: `http://localhost:8501`

La interfaz tiene 5 pestañas:

| Pestaña | Para qué sirve |
|---------|----------------|
| 🏠 Inicio | Estado de configuración y guía rápida |
| 📧 Correos | Ver y buscar la base de correos del Excel |
| 🚀 Procesar | Iniciar el procesamiento de nóminas |
| 📋 Resultados | Resumen del último procesamiento |
| 📊 Historial | Todos los envíos históricos con filtros |

### Modo CLI — para automatización

```bash
python src/main.py
```

Útil para programar la ejecución con el Programador de tareas de Windows o un cron de Linux.

---

## Flujo de procesamiento

Por cada archivo XML el sistema ejecuta estos pasos en orden:

```
1. Extraer nombre, CURP, UUID y datos del período del XML (CFDI 4.0)
2. Verificar si el UUID ya fue enviado (idempotencia — salta si ya existe)
3. Buscar el PDF correspondiente en el índice por CURP
4. Renombrar el PDF → NOMBRE_EMPLEADO-CURP.pdf (operación segura)
5. Buscar el correo del empleado en el Excel
6. Construir el asunto y cuerpo desde la plantilla
7. Enviar XML + PDF como adjuntos vía Microsoft Graph API
8. Registrar el envío en SQLite con todos los datos del recibo
```

Si cualquier paso falla, ese empleado se registra con error y el sistema continúa con el siguiente. La única excepción es un error de autenticación con Azure AD, que detiene el procesamiento completo.

---

## Personalizar el cuerpo del correo

Edita el archivo `templates/plantilla_correo.txt`. Puedes usar estas variables:

| Variable | Valor |
|----------|-------|
| `{nombre}` | Nombre completo del empleado |
| `{fecha_inicial}` | Inicio del período de la nómina |
| `{fecha_final}` | Fin del período de la nómina |
| `{total}` | Total a pagar |

Ejemplo:

```
Estimado(a) {nombre},

Adjunto encontrará su recibo de nómina del período
{fecha_inicial} al {fecha_final}.

Total a pagar: ${total}

Saludos cordiales,
Recursos Humanos — AGD Legal
```

---

## Logs

Cada ejecución queda registrada en `logs/nominas_YYYYMMDD.log`:

```
2025-04-05 10:23:01 | INFO     | nominas.procesador | Base de correos cargada: 103 válidos, 1 excluidos.
2025-04-05 10:23:02 | INFO     | nominas.procesador | Índice de PDFs construido: 104 CURPs indexados.
2025-04-05 10:23:03 | INFO     | nominas.procesador | [1/104] Correo enviado a JUAN PEREZ (juan@agdlegal.com)
2025-04-05 10:23:04 | WARNING  | nominas.procesador | [2/104] PDF no encontrado para MARIA LOPEZ (CURP: LOPM...)
2025-04-05 10:23:05 | INFO     | nominas.procesador | [3/104] Ya enviado anteriormente: CARLOS RUIZ (UUID: 963AF5BA...)
```

Un archivo por día. La ruta exacta se muestra en el sidebar de la interfaz web.

---

## Historial de envíos

El sistema guarda cada envío exitoso en `nominas.db` (SQLite). Esto sirve para:

- **Evitar reenvíos** si el script se interrumpe y se vuelve a ejecutar.
- **Auditoría**: saber qué se envió, a quién y cuándo.
- **Consultas**: filtrar por período, buscar empleados, exportar a CSV.

El historial es visible en la pestaña **📊 Historial** de la interfaz web.

---

## Tests

```bash
pytest
```

Para ver cobertura por módulo:

```bash
pip install pytest-cov
pytest --cov=src --cov-report=term-missing
```

---

## Resolución de problemas

**`Variable de entorno requerida no encontrada`**
→ Crea el archivo `.env` basado en `.env.example` y reinicia la aplicación.

**`Error de autenticación con Azure AD`**
→ Verifica los tres valores de Azure en `.env`. Asegúrate de que el permiso `Mail.Send` esté concedido (con ✅ verde) en el portal de Azure. Consulta [`docs/configurar_azure_ad.md`](docs/configurar_azure_ad.md).

**`PDF no encontrado para [empleado]`**
→ El CURP del XML no aparece en ningún PDF. El PDF debe ser digital (texto seleccionable), no un escáner. Verifica abriendo el PDF y seleccionando texto.

**`Correo inválido para [empleado]`**
→ El correo en el Excel tiene formato incorrecto. El log del día muestra el valor exacto que fue rechazado.

**`Correo no encontrado para [empleado]`**
→ El nombre del XML no coincide con ninguna entrada del Excel. El sistema normaliza tildes y mayúsculas, pero el nombre completo debe coincidir. El log muestra el nombre exacto que llegó del XML.

**El secreto de Azure expiró**
→ Genera uno nuevo en Azure AD → tu aplicación → Certificados y secretos → Nuevo secreto. Actualiza `AZURE_CLIENT_SECRET` en `.env`.

---

## Seguridad

- Las credenciales se cargan desde variables de entorno, nunca desde el código.
- El archivo `.env` y todos los archivos de datos están excluidos del repositorio.
- Los adjuntos tienen un límite de 20 MB antes de intentar el envío.
- El permiso `Mail.Send` de Azure AD es de solo escritura: no puede leer correos.
- El historial SQLite solo es accesible desde la máquina donde corre el sistema.

---

## Licencia

MIT — ver archivo [LICENSE](LICENSE) para detalles.
