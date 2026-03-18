# 💼 Sistema de Nóminas Automático

Sistema automatizado para el procesamiento y envío de recibos de nómina por correo electrónico. Lee archivos XML (CFDI 4.0 del SAT), los vincula con sus PDFs correspondientes por CURP, y envía ambos archivos al correo de cada empleado.

Desarrollado en Python con interfaz web usando Streamlit.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red)
![Tests](https://img.shields.io/badge/Tests-pytest-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## Características

- Procesamiento automático de archivos XML (CFDI 4.0)
- Vinculación de XMLs con PDFs por CURP mediante índice O(n)
- Renombrado seguro de PDFs (sin pérdida de datos ante interrupciones)
- Envío masivo de correos con XML y PDF adjuntos
- Validación de formato de correos electrónicos antes del envío
- Interfaz web con progreso en tiempo real
- Logs persistentes en archivo diario (`logs/nominas_YYYYMMDD.log`)
- Manejo de errores diferenciado por tipo (SMTP, archivos, validación)
- 50+ tests automatizados cubriendo todos los componentes críticos

---

## Estructura del proyecto

```
nominas-express/
├── src/
│   ├── app.py            # Interfaz web Streamlit
│   ├── main.py           # Modo CLI
│   ├── config.py         # Variables de entorno y rutas
│   ├── procesador.py     # Lógica de negocio principal
│   ├── correo.py         # Envío de emails (SMTP)
│   ├── logger.py         # Logging persistente a archivo
│   └── utilidades.py     # Normalización de nombres
├── tests/
│   ├── test_utilidades.py
│   ├── test_extraer_xml.py
│   ├── test_correo.py
│   ├── test_procesador_indice.py
│   ├── test_procesador_rename.py
│   ├── test_ejecutar_procesamiento.py
│   └── test_validacion_correos.py
├── .env.example          # Plantilla de configuración (copiar a .env)
├── .gitignore
├── pytest.ini
├── requirements.txt
└── README.md
```

Los datos de trabajo van fuera del repositorio (ver sección [Preparar datos](#3-preparar-datos)):

```
C:\Tu\ubicacion\de\Nominas\
├── XML\                          # Archivos XML del SAT
├── PDFs\                         # Recibos en PDF
└── correos_colaboradores.xlsx    # Base de correos
```

---

## Instalación

### Prerequisitos

- Python 3.10 o superior
- Cuenta de Gmail con verificación en 2 pasos activa

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/nominas-express.git
cd nominas-express
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Preparar datos

Crea la carpeta de trabajo y agrega los archivos necesarios:

```
C:\Tu\ubicacion\de\Nominas\
├── XML\
│   ├── nomina_empleado1.xml
│   └── nomina_empleado2.xml
├── PDFs\
│   ├── recibo_001.pdf
│   └── recibo_002.pdf
└── correos_colaboradores.xlsx
```

El archivo Excel debe tener exactamente estas dos columnas:

| Nombre | Correo |
|--------|--------|
| JUAN PEREZ GARCIA | juan.perez@empresa.com |
| MARIA LOPEZ SANCHEZ | maria.lopez@empresa.com |

> Los nombres deben coincidir con los del XML (con o sin tildes, el sistema los normaliza automáticamente).

### 4. Configurar credenciales

```bash
cp .env.example .env
```

Edita `.env` con tus valores reales:

```env
BASE_PATH=C:\Tu\ubicacion\de\Nominas

EMAIL_SENDER=tuusuario@gmail.com
EMAIL_PASSWORD=xxxx-xxxx-xxxx-xxxx
```

> ⚠️ **Nunca subas `.env` al repositorio.** Ya está incluido en `.gitignore`.

---

## Configurar Gmail

El sistema usa Gmail como servidor SMTP. Para que funcione necesitas una **contraseña de aplicación** (no tu contraseña normal de Gmail).

**Pasos:**

1. Activa la verificación en 2 pasos en tu cuenta Google
2. Ve a [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Crea una contraseña para "Correo" / "Otro dispositivo"
4. Copia los 16 caracteres generados y pégalos en `EMAIL_PASSWORD` de tu `.env`

> Si usas otro proveedor SMTP (Outlook, SendGrid, etc.), ajusta también `SMTP_SERVER` y `SMTP_PORT` en `.env`.

---

## Uso

### Interfaz web (recomendado)

```bash
streamlit run src/app.py
```

Accede en el navegador: `http://localhost:8501`

La interfaz incluye:
- Panel de control con estado de configuración y conteo de archivos
- Vista previa y búsqueda de la base de correos
- Procesamiento con barra de progreso y logs en tiempo real
- Reporte de resultados con tabla de detalle de errores

### Modo línea de comandos

```bash
python src/main.py
```

Útil para automatización o ejecución programada (tarea de Windows, cron).

---

## Flujo de procesamiento

Por cada archivo XML el sistema ejecuta estos pasos en orden:

```
1. Extraer nombre y CURP del XML (CFDI 4.0)
2. Buscar el PDF correspondiente en el índice por CURP
3. Renombrar el PDF → NOMBRE_EMPLEADO-CURP.pdf
4. Buscar el correo del empleado en el Excel
5. Enviar XML + PDF como adjuntos al correo encontrado
```

Si cualquier paso falla, ese empleado se registra como error y el sistema continúa con el siguiente. La única excepción es un error de autenticación SMTP, que detiene el procesamiento completo (no tiene sentido seguir si las credenciales son inválidas).

---

## Logs

Cada ejecución queda registrada en `logs/nominas_YYYYMMDD.log`:

```
2024-03-15 10:23:01 | INFO     | nominas.procesador | Base de correos cargada: 45 válidos, 1 excluidos.
2024-03-15 10:23:02 | INFO     | nominas.procesador | Índice de PDFs construido: 45 CURPs indexados.
2024-03-15 10:23:03 | INFO     | nominas.procesador | [1/45] Correo enviado a JUAN PEREZ (juan@empresa.com)
2024-03-15 10:23:04 | WARNING  | nominas.procesador | [2/45] PDF no encontrado para MARIA LOPEZ (CURP: LOPM850210MDFPRS09)
2024-03-15 10:23:05 | WARNING  | nominas.procesador | Correo inválido para 'CARLOS RUIZ': 'carlos.ruiz' — excluido.
```

Un archivo por día. La ruta exacta se muestra en el sidebar de la interfaz web.

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

Los tests cubren:

| Archivo | Qué verifica |
|---|---|
| `test_utilidades.py` | Normalización de nombres con tildes, espacios, mayúsculas |
| `test_extraer_xml.py` | Parsing de CFDI con XMLs reales del SAT |
| `test_correo.py` | Construcción de mensajes y validación de adjuntos |
| `test_procesador_indice.py` | Indexado O(n) de PDFs por CURP |
| `test_procesador_rename.py` | Renombrado seguro con simulación de crashes |
| `test_ejecutar_procesamiento.py` | Flujo completo con todas las ramas de error |
| `test_validacion_correos.py` | Validación de formato de correos electrónicos |

---

## Resolución de problemas

**`Variable de entorno requerida no encontrada: 'BASE_PATH'`**
→ Crea el archivo `.env` basado en `.env.example` y reinicia la aplicación.

**`Error de autenticación con Gmail`**
→ Verifica que `EMAIL_PASSWORD` sea una contraseña de aplicación (16 caracteres), no tu contraseña normal de Gmail.

**`PDF no encontrado para [empleado]`**
→ El CURP en el XML no aparece en ningún PDF. Verifica que el PDF sea digital (texto seleccionable) y no un escáner.

**`Correo inválido para [empleado]`**
→ El correo en el Excel tiene un formato incorrecto. Revisa el archivo y corrige la dirección. El log del día muestra exactamente qué valor fue rechazado.

**`Correo no encontrado para [empleado]`**
→ El nombre en el XML no coincide con ninguna entrada del Excel. Revisa el log para ver el nombre exacto que llegó del XML y ajusta el Excel. El sistema normaliza tildes y mayúsculas automáticamente, pero el nombre completo debe coincidir.

---

## Seguridad

- Las credenciales se cargan desde variables de entorno, nunca desde el código fuente
- El archivo `.env` está excluido del repositorio por `.gitignore`
- Los archivos de datos (XMLs, PDFs, Excel) también están excluidos
- Los adjuntos tienen un límite de 20 MB antes de intentar el envío

---

## Licencia

MIT — ver archivo [LICENSE](LICENSE) para detalles.