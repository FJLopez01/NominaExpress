"""
tests/test_extraer_xml.py

Cobertura de extraer_datos_xml().

Se usan XMLs sintéticos con la estructura real del SAT (CFDI 4.0 + nomina12).
Esto documenta el contrato esperado del XML y detecta inmediatamente
si el SAT cambia el schema o si hay un error de namespace.

Ejecutar:
    pytest tests/test_extraer_xml.py -v
"""

import textwrap
from pathlib import Path

import pytest

from procesador import extraer_datos_xml

# ------------------------------------------------------------------
# XMLs de prueba — estructura real del SAT (CFDI 4.0 + nomina12)
# ------------------------------------------------------------------

XML_VALIDO = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <cfdi:Comprobante
        xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
        xmlns:nomina12="http://www.sat.gob.mx/nomina12"
        Version="4.0"
        TipoDeComprobante="N">
      <cfdi:Receptor
          Nombre="JUAN PÉREZ GARCÍA"
          Rfc="PEGJ900101ABC"
          UsoCFDI="CN01"/>
      <cfdi:Complemento>
        <nomina12:Nomina
            TipoNomina="O"
            FechaPago="2024-01-15">
          <nomina12:Receptor
              Curp="PEGJ900101HDFRZN01"
              NumSeguridadSocial="12345678901"/>
        </nomina12:Nomina>
      </cfdi:Complemento>
    </cfdi:Comprobante>
""")

XML_CURP_MINUSCULAS = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <cfdi:Comprobante
        xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
        xmlns:nomina12="http://www.sat.gob.mx/nomina12">
      <cfdi:Receptor Nombre="MARIA LOPEZ"/>
      <cfdi:Complemento>
        <nomina12:Nomina>
          <nomina12:Receptor Curp="lopm850210mdfprs09"/>
        </nomina12:Nomina>
      </cfdi:Complemento>
    </cfdi:Comprobante>
""")

XML_SIN_RECEPTOR_NOMINA = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <cfdi:Comprobante
        xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
        xmlns:nomina12="http://www.sat.gob.mx/nomina12">
      <cfdi:Receptor Nombre="CARLOS RUIZ"/>
      <cfdi:Complemento>
        <nomina12:Nomina/>
      </cfdi:Complemento>
    </cfdi:Comprobante>
""")

XML_MALFORMADO = "esto no es xml válido <<<"

XML_VACIO = ""


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def crear_xml(tmp_path: Path, nombre_archivo: str, contenido: str) -> Path:
    f = tmp_path / nombre_archivo
    f.write_text(contenido, encoding="utf-8")
    return f


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

class TestExtraerDatosXml:

    def test_extrae_nombre_y_curp_correctamente(self, tmp_path):
        xml = crear_xml(tmp_path, "nomina.xml", XML_VALIDO)
        nombre, curp = extraer_datos_xml(str(xml))

        assert nombre == "JUAN PÉREZ GARCÍA"
        assert curp == "PEGJ900101HDFRZN01"

    def test_curp_siempre_en_mayusculas(self, tmp_path):
        """
        El SAT emite CURPs en mayúsculas, pero si llega en minúsculas
        (error del proveedor) debe normalizarse para que el índice funcione.
        """
        xml = crear_xml(tmp_path, "nomina.xml", XML_CURP_MINUSCULAS)
        _, curp = extraer_datos_xml(str(xml))

        assert curp == curp.upper()

    def test_xml_sin_nodo_receptor_nomina_retorna_none(self, tmp_path):
        """
        Si falta el nodo nomina12:Receptor (XML incompleto del proveedor),
        debe retornar (None, None) sin lanzar excepción.
        """
        xml = crear_xml(tmp_path, "nomina.xml", XML_SIN_RECEPTOR_NOMINA)
        nombre, curp = extraer_datos_xml(str(xml))

        assert nombre is None
        assert curp is None

    def test_xml_malformado_retorna_none(self, tmp_path):
        xml = crear_xml(tmp_path, "nomina.xml", XML_MALFORMADO)
        nombre, curp = extraer_datos_xml(str(xml))

        assert nombre is None
        assert curp is None

    def test_archivo_inexistente_retorna_none(self, tmp_path):
        nombre, curp = extraer_datos_xml(str(tmp_path / "no_existe.xml"))

        assert nombre is None
        assert curp is None

    def test_xml_vacio_retorna_none(self, tmp_path):
        xml = crear_xml(tmp_path, "nomina.xml", XML_VACIO)
        nombre, curp = extraer_datos_xml(str(xml))

        assert nombre is None
        assert curp is None

    def test_no_lanza_excepcion_ante_xml_invalido(self, tmp_path):
        """
        Garantía de robustez: extraer_datos_xml NUNCA debe propagar
        una excepción. El caller espera (None, None) como señal de error.
        """
        xml = crear_xml(tmp_path, "nomina.xml", XML_MALFORMADO)
        try:
            extraer_datos_xml(str(xml))
        except Exception as e:
            pytest.fail(f"extraer_datos_xml lanzó una excepción inesperada: {e}")