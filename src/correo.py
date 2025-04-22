import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from config import EMAIL_SENDER, EMAIL_PASSWORD, SMTP_SERVER, SMTP_PORT

def enviar_correo(destinatario, asunto, cuerpo, archivos_adjuntos):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = destinatario
    msg['Subject'] = asunto
    msg.attach(MIMEText(cuerpo, 'plain'))

    for archivo in archivos_adjuntos:
        part = MIMEBase('application', 'octet-stream')
        with open(archivo, 'rb') as f:
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{archivo.split(os.sep)[-1]}"')
        msg.attach(part)

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
            print(f"✅ Correo enviado a {destinatario}")
    except Exception as e:
        print(f"❌ Error al enviar correo a {destinatario}: {str(e)}")
