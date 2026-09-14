import sqlite3
from api_libros.excepciones import LibroNoEncontrado

class DatosLibrosSQLite:
    def __init__(self, nombre_archivo):
        self.conexion = sqlite3.connect(database=nombre_archivo, check_same_thread=False)
        # filas puede comportarse como dicts, si lo quito son tuplas
        # self.conexion.row_factory = sqlite3.Row
        self.crear_tabla_inicial()

    # uso interno ~ private; _interno, __oculto: mangling
    def _fila_to_dict(self, fila: tuple[str | int]) -> dict[str, str | int]:
        return {
            "id": fila[0],
            "Libro": fila[1],
            "Autor": fila[2]
        }

    def crear_tabla_inicial(self):
        self.cursor = self.conexion.cursor()
        sql = """
            CREATE TABLE IF NOT EXISTS libros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                libro TEXT NOT NULL,
                autor TEXT NOT NULL
            );
            """ # sin UNIQUE para libro
        self.cursor.execute(sql)
        self.conexion.commit() # tras commit, se cierra la conexion

    def get_all_books(self) -> list[dict[str,str]]:
        self.cursor = self.conexion.cursor()
        sql = """
            SELECT id, libro, autor
            FROM libros
            """
        self.cursor.execute(sql)
        # tuplas con los elementos
        filas = self.cursor.fetchall()
        
        return [
            self._fila_to_dict(fila)
            for fila in filas
        ]
    
    def get_book(self, id: int) -> dict[str, str | int]:
        self.cursor = self.conexion.cursor()
        sql = """
            SELECT id, libro, autor
            FROM libros
            WHERE id = ?
            """
        self.cursor.execute(sql, (id, )) # placeholder espera tupla, coma necesaria
        # (1, "Niebla", "Unamuno") es una tupla
        fila = self.cursor.fetchone()
        if not fila:
            raise LibroNoEncontrado(id)
        return self._fila_to_dict(fila)

    def save_book(self, data: dict[str, str]) -> dict[str, str | int]:
        self.cursor = self.conexion.cursor()
        sql = """INSERT INTO libros (libro, autor) VALUES (:Libro, :Autor);"""
        self.cursor.execute(sql, data)
        self.conexion.commit()
        data['id'] = self.cursor.lastrowid
        return data
    
    def update_book(self, id: int, data:dict[str, str]) -> dict[str, str | int]:
        self.cursor = self.conexion.cursor()
        sql = """
            UPDATE libros
            SET Libro = :Libro, Autor = :Autor
            WHERE id = :id;
        """
        data['id'] = id
        self.cursor.execute(sql, data)
        self.conexion.commit()
        if self.cursor.rowcount == 0:
            raise LibroNoEncontrado(id)
        return data

    def delete_book(self, id: int) -> dict[str, str | int] | None:
        self.cursor = self.conexion.cursor()
        sql = """
            DELETE
            FROM libros
            WHERE id = ?
            RETURNING id, libro, autor;
        """
        self.cursor.execute(sql, (id, ))
        fila = self.cursor.fetchone()
        self.conexion.commit()
        if not fila:
            raise LibroNoEncontrado(id)
        return self._fila_to_dict(fila)
    
    def list_book(self, page: int, size: int) -> list[dict[str, str]]:
        offset = (page - 1)*size
        limit = size
        self.cursor = self.conexion.cursor()
        sql = """
            SELECT id, libro, autor
            FROM libros
            ORDER BY id ASC
            LIMIT ? OFFSET ?;
        """
        # offset(inicio) - cuantas filas saltar; limit cuantas filas devolver(size)
        self.cursor.execute(sql, (limit, offset, ))
        #self.conexion.commit() - no hace falta en un select
        filas = self.cursor.fetchall()
        return [
            self._fila_to_dict(fila)
            for fila in filas
        ]