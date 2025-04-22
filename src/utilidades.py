import unicodedata

def limpiar_nombre(nombre):
    nfkd = unicodedata.normalize('NFKD', nombre)
    sin_tildes = ''.join([c for c in nfkd if not unicodedata.combining(c)])
    return sin_tildes.strip().replace(" ", "_").upper()

def normalizar_nombre_para_busqueda(nombre):
    nfkd = unicodedata.normalize('NFKD', nombre)
    sin_tildes = ''.join([c for c in nfkd if not unicodedata.combining(c)])
    return sin_tildes.strip().replace(" ", "").replace("_", "").upper()
