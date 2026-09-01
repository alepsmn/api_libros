class LibroNoEncontrado(Exception):
    def __init__(self, id):
        mensaje = f"""El libro con id: {id}, no ha sido encontrado"""
        super().__init__(mensaje)

class EstructuraLibroInvalida(Exception):
    def __init__(self, data: dict[str, str], campos_requeridos: set[str]):
        mensaje = f"""Estructura introducida: {data.keys()} - Incompatible con la esperada: {campos_requeridos}"""
        super().__init__(mensaje)