from api_libros.excepciones import LibroNoEncontrado

class DatosLibros:

    def __init__(self):
        # Inicialmente habra una unica instancia, tiene su propio contador
        # Todos los datos lo usaran como "armadura" -> pasaran por ella
        self.contador = 0
        self.libros = {}

    def get_all_books(self) -> dict[dict[str,str]]:
        return self.libros
    
    def get_book(self, id: int) -> dict[str, str | int]:
        if id not in self.libros:
            raise LibroNoEncontrado(id)
        return self.libros[id]
    
    def save_book(self, data: dict[str, str]) -> dict[str, str | int]:
        data['id'] = self.contador
        self.libros[self.contador] = data
        self.contador += 1
        return data
    
    def update_book(self, id: int, data:dict[str, str]) -> dict[str, str | int]:
        if id not in self.libros:
            raise LibroNoEncontrado(id)
        self.libros[id] = data
        return data
    
    def delete_book(self, id: int) -> dict[str, str | int] | None:
        if id not in self.libros:
            raise LibroNoEncontrado(id)
        borrado = self.libros.pop(id, None)
        return borrado
    
    def list_book(self, page: int, size: int) -> list[dict[str, str]]:
        todos = list(self.libros.values())
        inicio = (page - 1)*size
        fin = inicio + size
        return todos[inicio:fin]