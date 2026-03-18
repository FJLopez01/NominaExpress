"""
tests/test_utilidades.py

Cobertura de normalizar_nombre_para_busqueda() y limpiar_nombre().

Estos son los tests más críticos del proyecto: un bug aquí hace
que NINGÚN correo se encuentre en el Excel, fallando silenciosamente
para todos los empleados sin una causa obvia.

Ejecutar:
    pytest tests/test_utilidades.py -v
"""

import pytest
from utilidades import limpiar_nombre, normalizar_nombre_para_busqueda


class TestNormalizarNombreParaBusqueda:
    """
    normalizar_nombre_para_busqueda() se usa como clave de búsqueda
    en el diccionario de correos. El nombre del XML y el nombre del
    Excel deben producir exactamente la misma clave para que el lookup
    funcione. Cualquier diferencia en espacios, tildes o mayúsculas
    rompe el matching silenciosamente.
    """

    def test_nombre_simple_sin_tildes(self):
        assert normalizar_nombre_para_busqueda("JUAN PEREZ") == "JUANPEREZ"

    def test_nombre_con_tildes(self):
        assert normalizar_nombre_para_busqueda("JOSÉ GARCÍA") == "JOSEGARCIA"

    def test_nombre_con_multiples_tildes(self):
        assert normalizar_nombre_para_busqueda("MARÍA RODRÍGUEZ LÓPEZ") == "MARIARODRIGUEZLOPEZ"

    def test_nombre_en_minusculas(self):
        assert normalizar_nombre_para_busqueda("juan perez garcia") == "JUANPEREZGARCIA"

    def test_nombre_en_mixto(self):
        assert normalizar_nombre_para_busqueda("Juan Pérez García") == "JUANPEREZGARCIA"

    def test_espacios_multiples(self):
        # Nombres con doble espacio entre palabras (error común en Excel)
        assert normalizar_nombre_para_busqueda("JUAN  PEREZ") == "JUANPEREZ"

    def test_espacios_al_inicio_y_final(self):
        assert normalizar_nombre_para_busqueda("  JUAN PEREZ  ") == "JUANPEREZ"

    def test_nombre_con_guiones_bajos(self):
        # Puede venir del limpiar_nombre aplicado antes
        assert normalizar_nombre_para_busqueda("JUAN_PEREZ") == "JUANPEREZ"

    def test_nombre_vacio(self):
        assert normalizar_nombre_para_busqueda("") == ""

    def test_solo_espacios(self):
        assert normalizar_nombre_para_busqueda("   ") == ""

    def test_nombre_con_enye(self):
        assert normalizar_nombre_para_busqueda("NUÑEZ") == "NUNEZ"

    def test_nombre_con_u_dieresis(self):
        assert normalizar_nombre_para_busqueda("GÜERO") == "GUERO"

    @pytest.mark.parametrize("xml_nombre, excel_nombre", [
        ("JUAN PÉREZ GARCÍA",     "Juan Pérez García"),
        ("MARÍA LÓPEZ SÁNCHEZ",   "MARIA LOPEZ SANCHEZ"),
        ("JOSÉ MARTÍNEZ NÚÑEZ",   "jose martinez nunez"),
        ("ANA  TORRES  RUIZ",     "ANA TORRES RUIZ"),   # espacios dobles en XML
    ])
    def test_xml_y_excel_producen_la_misma_clave(self, xml_nombre, excel_nombre):
        """
        El caso de uso real: el nombre del XML y el del Excel
        deben coincidir después de normalizar, aunque vengan
        en formatos distintos.
        """
        assert (
            normalizar_nombre_para_busqueda(xml_nombre)
            == normalizar_nombre_para_busqueda(excel_nombre)
        )


class TestLimpiarNombre:
    """
    limpiar_nombre() genera el componente del nombre en el
    nombre de archivo del PDF: JUAN_PEREZ_GARCIA-CURP.pdf
    """

    def test_espacios_reemplazados_por_guiones_bajos(self):
        assert limpiar_nombre("JUAN PEREZ GARCIA") == "JUAN_PEREZ_GARCIA"

    def test_tildes_eliminadas(self):
        assert limpiar_nombre("JOSÉ GARCÍA") == "JOSE_GARCIA"

    def test_resultado_en_mayusculas(self):
        assert limpiar_nombre("juan perez") == "JUAN_PEREZ"

    def test_nombre_con_enye(self):
        assert limpiar_nombre("NUÑEZ CORONA") == "NUNEZ_CORONA"

    def test_espacios_extremos_eliminados(self):
        assert limpiar_nombre("  JUAN PEREZ  ") == "JUAN_PEREZ"

    def test_nombre_simple(self):
        assert limpiar_nombre("GARCIA") == "GARCIA"

    @pytest.mark.parametrize("entrada,esperado", [
        ("ANDRÉS TORRES",       "ANDRES_TORRES"),
        ("María Rodríguez",     "MARIA_RODRIGUEZ"),
        ("HÉCTOR MUÑOZ PEÑA",   "HECTOR_MUNOZ_PENA"),
    ])
    def test_parametrizado(self, entrada, esperado):
        assert limpiar_nombre(entrada) == esperado