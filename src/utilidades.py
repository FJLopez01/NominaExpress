"""
utilidades.py — Funciones auxiliares de normalización de texto.

Usadas para hacer coincidencia entre nombres del XML y del Excel,
independientemente de tildes, mayúsculas o espacios.
"""

import unicodedata


def limpiar_nombre(nombre: str) -> str:
    """
    Normaliza un nombre para usarlo como parte del nombre de archivo del PDF.

    Elimina tildes, convierte a mayúsculas y reemplaza espacios por guiones bajos.

    Ejemplo:
        "Juan Pérez García" → "JUAN_PEREZ_GARCIA"
    """
    nfkd = unicodedata.normalize("NFKD", nombre)
    sin_tildes = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sin_tildes.strip().replace(" ", "_").upper()


def normalizar_nombre_para_busqueda(nombre: str) -> str:
    """
    Normaliza un nombre para usarlo como clave de búsqueda en el diccionario
    de correos. Elimina tildes, espacios, guiones bajos y convierte a mayúsculas.

    El nombre del XML y el nombre del Excel deben producir la misma clave
    para que el lookup funcione correctamente.

    Ejemplo:
        "Juan Pérez García"  → "JUANPEREZGARCIA"
        "JUAN PEREZ GARCIA"  → "JUANPEREZGARCIA"
        "juan_perez_garcia"  → "JUANPEREZGARCIA"
    """
    nfkd = unicodedata.normalize("NFKD", nombre)
    sin_tildes = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sin_tildes.strip().replace(" ", "").replace("_", "").upper()