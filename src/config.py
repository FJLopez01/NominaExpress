import os

# Rutas
BASE_PATH = r"C:\Tu\ubicacion\de\Nominas" 
XML_PATH = os.path.join(BASE_PATH, "XML")
PDF_PATH = os.path.join(BASE_PATH, "PDFs")
EXCEL_CORREOS = os.path.join(BASE_PATH, "correos_colaboradores.xlsx")

# Configuración de correo
EMAIL_SENDER = "tuusuario@gmail.com"
EMAIL_PASSWORD = "tucontraseñasdeaplicaciones"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
