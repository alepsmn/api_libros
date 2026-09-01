from api_libros.excepciones import EstructuraLibroInvalida

# Otro posible mejor nombre: ServiciosLibros / BookService
class ServiceValidation:
    def __init__(self, storage):
        self.campos_requeridos = {"Libro", "Autor"}
        self.storage = storage

    # Futuro: val da info al handler detalle de implementacion que no importa - quitar?
    def val_get_all_books(self):
        return self.storage.get_all_books()

    def val_get_book(self, id: int):
        return self.storage.get_book(id)

    def val_save_book(self, data: dict[str, str]):
        posted_keys = set(data.keys())
        if not self.campos_requeridos.issubset(posted_keys):
            raise EstructuraLibroInvalida(data, self.campos_requeridos)
        return  self.storage.save_book(data)

    def val_update_book(self, id: int, data: dict[str, str]):
        posted_keys = set(data.keys())
        if not self.campos_requeridos.issubset(posted_keys):
            raise EstructuraLibroInvalida(data, self.campos_requeridos)
        return self.storage.update_book(id, data)

    def val_delete_book(self, id: int):
        return self.storage.delete_book(id)

    def val_list_book(self, page:int, size:int):
        return self.storage.list_book(page, size)