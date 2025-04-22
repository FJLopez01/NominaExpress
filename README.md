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




