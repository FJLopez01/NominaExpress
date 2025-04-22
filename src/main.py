import os
from config import XML_PATH, PDF_PATH
from procesador import leer_correos_excel, extraer_datos_xml, buscar_pdf_por_curp
from utilidades import limpiar_nombre, normalizar_nombre_para_busqueda
from correo import enviar_correo

correos_por_nombre = leer_correos_excel()

for xml_file in os.listdir(XML_PATH):
    if not xml_file.endswith(".xml"):
        continue

    xml_path = os.path.join(XML_PATH, xml_file)
    nombre, curp = extraer_datos_xml(xml_path)
    if not nombre or not curp:
        continue

    nombre_limpio = limpiar_nombre(nombre)
    pdf_path, original_pdf = buscar_pdf_por_curp(curp)

    if pdf_path:
        nuevo_nombre = f"{nombre_limpio}-{curp}.pdf"
        nuevo_path = os.path.join(PDF_PATH, nuevo_nombre)

        if not os.path.exists(nuevo_path):
            os.rename(pdf_path, nuevo_path)
            print(f"📄 Renombrado: {original_pdf} -> {nuevo_nombre}")

        # Enviar correo
        clave = normalizar_nombre_para_busqueda(nombre)
        correo = correos_por_nombre.get(clave)

        if correo:
            asunto = f"Recibo de Nómina - {nombre}"
            cuerpo = f"""Estimado(a): {nombre}, 

Por medio del presente reciba un cordial saludo y al mismo tiempo enviamos en archivo adjunto el CFDI con el formato electrónico XML(s) de las remuneraciones cubiertas en el período indicado en el título del correo.
"""
            enviar_correo(correo, asunto, cuerpo, [xml_path, nuevo_path])
        else:
            print(f"⚠️ Correo no encontrado para: {nombre}")
