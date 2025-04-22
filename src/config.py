import os

# Rutas
BASE_PATH = r"C:\Users\SISTEMAS AUX\Desktop\Nominas" 
XML_PATH = os.path.join(BASE_PATH, "XML")
PDF_PATH = os.path.join(BASE_PATH, "PDFs")
EXCEL_CORREOS = os.path.join(BASE_PATH, "correos_colaboradores_prueba.xlsx")

# Configuración de correo
EMAIL_SENDER = "tuusuario@gmail.com"
EMAIL_PASSWORD = "pbbkwaodxelgffgz"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
