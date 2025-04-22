# NominaExpress

## 📤 Automatización de Envío de Nóminas

Este proyecto automatiza el envío de recibos de nómina a los colaboradores de una empresa, adjuntando los archivos XML y PDF correspondientes, basándose en su CURP y nombre.

## 🛠️ Tecnologías
- Python 3
- Pandas
- smtplib (correo)
- PyPDF2
- dotenv (manejo seguro de credenciales)

## 📁 Estructura del proyecto

```
automated-payroll-dispatcher/
├── src/
│   ├── main.py                   # Script principal
│   ├── config.py                 # Variables de entorno y rutas
│   ├── procesador.py             # Lectura XML, PDF y Excel
│   ├── correo.py                 # Lógica de envío de correos
│   └── utilidades.py             # Funciones de normalización
│
├── data/
│   └── correos_colaboradores_ejemplo.xlsx    # Archivo de ejemplo con nombres y correos
│
├── .env.example                 # Plantilla para variables de entorno
├── .gitignore
├── requirements.txt
└── README.md
```

## ⚙️ Uso

1. Clona este repositorio:
```bash
git clone https://github.com/tuusuario/NominaExpress.git
cd NominaExpress
```
2. Instala las dependencias:
```bash
pip install -r requirements.txt
```
3. Crea un archivo .env basado en .env.example y añade tus datos.

### ✅ `.env.example`

```env
# Credenciales del correo
EMAIL_SENDER=tuemail@gmail.com
EMAIL_PASSWORD=tu_contraseña_de_aplicación
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587

# Ruta base donde están las carpetas XML, PDFs y Excel
BASE_PATH=C:\ruta\a\tu\carpeta\Nominas
```

5. Ejecuta el script principal:
```bash
python src/main.py
```



