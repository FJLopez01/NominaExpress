import os
import xml.etree.ElementTree as ET
import pandas as pd
from PyPDF2 import PdfReader
from utilidades import limpiar_nombre, normalizar_nombre_para_busqueda
from config import XML_PATH, PDF_PATH, EXCEL_CORREOS

def leer_correos_excel():
    df = pd.read_excel(EXCEL_CORREOS)
    df.columns = df.columns.str.strip()
    df['Nombre'] = df['Nombre'].astype(str)
    df['Nombre_normalizado'] = df['Nombre'].apply(normalizar_nombre_para_busqueda)
    return dict(zip(df['Nombre_normalizado'], df['Correo']))

def extraer_datos_xml(xml_file):
    namespaces = {
        'cfdi': 'http://www.sat.gob.mx/cfd/4',
        'nomina12': 'http://www.sat.gob.mx/nomina12'
    }

    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        nombre = root.find(".//cfdi:Receptor", namespaces).attrib.get("Nombre")
        curp = root.find(".//nomina12:Receptor", namespaces).attrib.get("Curp").upper()
        return nombre, curp
    except Exception as e:
        print(f"❌ Error en {xml_file}: {e}")
        return None, None

def buscar_pdf_por_curp(curp):
    for pdf_file in os.listdir(PDF_PATH):
        if not pdf_file.endswith(".pdf"):
            continue

        path = os.path.join(PDF_PATH, pdf_file)

        try:
            contenido = ""
            with open(path, "rb") as f:
                reader = PdfReader(f)
                for page in reader.pages:
                    contenido += page.extract_text()

            if curp in contenido:
                return path, pdf_file
        except Exception as e:
            print(f"❌ PDF inválido {pdf_file}: {e}")
    return None, None
