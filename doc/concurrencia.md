# Peldaño 1 — Concurrencia: hilos, races y locks

Notas de trabajo. Material en bruto para que escribas las tuyas.
Contexto: `api_libros` como gimnasio. Peldaño 1 de la escalera: `ThreadingHTTPServer`
+ race condition demostrada con test antes del lock.

---

## 1. El punto de partida: qué cambia al meter hilos

`HTTPServer` atiende **una petición cada vez**. Acepta la conexión, ejecuta el handler,
espera a que termine, y solo entonces acepta la siguiente. Un único hilo. Nada se solapa,
así que nada se corrompe. Es seguro por ser lento.

`ThreadingHTTPServer` = `HTTPServer` + `ThreadingMixIn`. Por cada conexión aceptada
**lanza un hilo nuevo** que ejecuta el handler. Diez peticiones simultáneas = diez hilos
dentro de `do_POST` a la vez.

El detalle decisivo: esos hilos comparten **un solo objeto `RawData`**. Se crea una vez en
`run()` y se cuelga de `self.server`. No hay una copia por hilo. Todos escriben sobre el
mismo `self.jobs` y el mismo `self.counter`.

> **Memoria compartida mutable + ejecución solapada = el problema entero de la
> concurrencia.** Todo lo demás son detalles.

Nota: `ThreadingHTTPServer.daemon_threads = True` por defecto. Los hilos de petición no
impiden que el proceso muera.

Pendiente de responder: ¿cuántos hilos puede llegar a crear? ¿quién los destruye? (La
respuesta importa en el peldaño 4, backpressure.)

---

## 2. Anatomía de la race en `save()`

```python
def save(self, data):
    data['id'] = self.counter          # lectura 1 de counter
    self.jobs[self.counter] = data     # lectura 2 de counter
    self.counter += 1                  # lectura 3 + escritura
    return data
```

El patrón se llama **read-modify-write**: lees un valor, calculas uno nuevo a partir del que
leíste, lo escribes. Si entre la lectura y la escritura otro hilo hace lo mismo, uno de los
dos trabaja con un valor caducado y pisa al otro.

Dato clave que me costó ver: **cada mención de un atributo compartido es una lectura nueva.**
`self.counter` tres veces = tres lecturas en tres instantes distintos. No es una lectura con
tres usos. Y la clave del dict es `self.counter`, no `data['id']` — son dos lecturas
distintas en dos momentos distintos.

### Intercalado: definición correcta

Un intercalado válido es cualquier fusión de las dos secuencias que **respete el orden
interno de cada hilo**. Entre dos pasos de A puede colarse cualquier cantidad de pasos de B:
cero, uno, todos. Alternar uno y uno es *un* intercalado posible, no la definición.

Con 3 pasos por hilo hay 20 fusiones posibles. La mayoría dan el resultado correcto. Unas
pocas no. El trabajo del análisis no es predecir cuál ocurrirá, es responder:
**¿existe al menos uno que rompa el invariante?** Si existe, tarde o temprano ocurre.

Es el mismo diagrama de *schedules* de BBDD, y la anomalía es la misma: **lost update**.
Y el criterio de corrección también es el mismo: un schedule concurrente es correcto si y
solo si es **equivalente a alguna ejecución secuencial**.

### Traza (a) — pérdida de datos

Orden `A1, B1, A2, B2, A3, B3`. Inicial: `counter = 7`, `jobs = {}`.

| t | acción | counter | jobs |
|---|--------|---------|------|
| 1 | A: `data['id'] = counter` | 7 | `{}` |
| 2 | B: `data['id'] = counter` | 7 | `{}` |
| 3 | A: `jobs[counter] = data` | 7 | `{7: {id:7, A}}` |
| 4 | B: `jobs[counter] = data` | 7 | `{7: {id:7, B}}` ← pisa a A |
| 5 | A: `counter += 1` | 8 | igual |
| 6 | B: `counter += 1` | 9 | igual |

Resultado: dos respuestas `201` al cliente, **un** job guardado. Y `counter` en 9 → el id 8
queda quemado, nunca existirá. Dos incrementos, un slot ocupado.

### Traza (b) — corrupción de identidad

Orden `A1, B1, A2, A3, B2, B3`.

| t | acción | counter | jobs |
|---|--------|---------|------|
| 1 | A: `data['id'] = counter` | 7 | `{}` |
| 2 | B: `data['id'] = counter` | 7 | `{}` |
| 3 | A: `jobs[counter] = data` | 7 | `{7: {id:7, A}}` |
| 4 | A: `counter += 1` | 8 | `{7: {id:7, A}}` |
| 5 | B: `jobs[counter] = data` | 8 | `{7:{id:7,A}, 8:{id:7,B}}` |
| 6 | B: `counter += 1` | 9 | igual |

Resultado: **dos** jobs, ninguno perdido, y `jobs[8]` contiene un objeto que afirma ser el
id 7.

Daños de cara al cliente:
- El cliente B recibe `201 {"id": 7}` y guarda el 7 como referencia. Cada `GET /jobs/7` le
  devuelve **el job de A**. Su `DELETE /jobs/7` borra el trabajo ajeno.
- Su propio job existe en la clave 8 y es inalcanzable: nadie conoce ese número.
- El recuento total cuadra → la monitorización dice que todo va bien.

> (a) pierde datos y te enteras. (b) conserva los datos y corrompe la identidad, y no te
> enteras nunca. **(b) es peor.**

### Observación de diseño

Si la línea 2 fuera `self.jobs[data['id']] = data`, la avería (b) desaparecería: una sola
lectura de `counter` por `save()`, las dos claves coincidirían, y todo colapsaría al caso (a).
No arregla la race, pero **menos lecturas de estado compartido = menos modos de fallo.**
Al meter el lock, no basta con envolver: conviene además dejar de leer la variable tres veces.

---

## 3. Lo que el GIL garantiza y lo que no

El GIL garantiza que **solo un hilo ejecuta bytecode de Python en cada instante**.

De ahí la conclusión falsa habitual: "entonces en Python no hay races". Falso.

El GIL protege **una instrucción de bytecode**. No una línea mía, ni un bloque.
`self.counter += 1` son tres bytecodes y el GIL no los une.

### Dónde puede conmutar de hilo

No en cualquier punto. Solo en **puntos de cesión**:
- el hilo hace I/O o se duerme → suelta el GIL voluntariamente
- el intérprete llega a uno de sus puntos de control y ya pasó el turno
  (`sys.getswitchinterval()`, 5 ms por defecto)

CPython **no alterna instrucción a instrucción**. Coge un hilo y lo ejecuta de corrido
durante miles de bytecodes.

Consecuencia: de los 20 intercalados *concebibles* sobre papel, solo son **realizables**
aquellos cuyo corte cae en un punto de cesión.

### Mediciones (CPython 3.12)

| escenario | esperados | guardados |
|---|---|---|
| `RawData` real, 16 hilos × 60 POSTs HTTP | 960 | 960 |
| puro Python, 16 hilos × 500 inserciones | 8000 | 8000 |
| idem con `sys.setswitchinterval(1e-6)` | 8000 | 8000 |
| variante con llamada a método Python en la sección crítica | 8000 | 8000 |
| variante con **punto de cesión real** en la sección crítica | 8000 | **~520** |

`save()` es código recto: sin bucle, sin I/O, sin espera. **No hay ningún punto de cesión
entre la lectura y la escritura del contador.** Por eso el papel dice "está roto" y la
máquina responde 960/960.

### Las dos afirmaciones son ciertas a la vez

- El código es **incorrecto**: el invariante depende de un intercalado que no he prohibido.
- El código **no falla hoy**: el planificador no genera ese intercalado, por un detalle de
  implementación de este intérprete y esta versión.

> Un test que no dispara la race no demuestra que el código sea seguro. Demuestra que el
> test es débil.

El lock no hace falta porque falle. Hace falta porque **elimina los intercalados malos por
construcción**, en vez de confiar en que el planificador tenga a bien no generarlos.

---

## 4. Dos ejes que confundí: compartido/local y mutable/inmutable

Son **independientes**.

- **Compartido** = alcanzable desde más de un hilo. Propiedad de *visibilidad*.
- **Mutable** = se puede modificar en sitio. Propiedad del *tipo*.

Refutación directa de "la race viene de la mutabilidad": **`self.counter` es un `int`, y los
`int` son inmutables en Python.** Y es el que revienta.

`self.counter += 1` no modifica el 7 — el 7 no se toca. **Rebindea el atributo** `counter`
del objeto `RawData` para que apunte a un 8 nuevo. Ese hueco, dentro de un objeto que todos
los hilos alcanzan, sí es compartido y sí cambia.

Con la lista es al revés: la referencia nunca cambia; cambia el contenido, en sitio. Dos
mecanismos distintos de modificación, **ambos sobre estado compartido**.

### El criterio real, en dos preguntas

1. **¿Es alcanzable desde varios hilos?** Si no → seguro, fin. Una variable local de la
   función worker es privada aunque sea una lista enorme. `data` dentro de `save()` es
   privada por hilo — por eso `data['id'] = 7` no tuvo nada que ver con el fallo.
2. **Si es compartida: ¿la actualización es atómica y sin read-modify-write?**

> El criterio es **cómo se actualiza**, no **de qué tipo es**.

Y la mitad del trabajo de escribir código concurrente consiste en reducir el estado
compartido a favor del local.

---

## 5. Atomicidad vs. read-modify-write

`lst.append(x)` es seguro entre hilos. `self.counter += 1` no. Por **dos** propiedades
distintas, y hay que separarlas:

**Propiedad 1 — es atómica.** `append` es una sola llamada a código C que se ejecuta de
principio a fin con el GIL cogido y no lo suelta por el camino. Ningún hilo puede observar
la lista a medio modificar. `+= 1` son tres bytecodes con dos huecos.

**Propiedad 2 — no hay read-modify-write en mi código.** Con el contador leo un valor, lo uso
para calcular, y escribo; si lo leído está caducado, piso. Con `append` no leo nada: digo
"pon esto al final", y *cuál es el final* lo resuelve la propia operación atómica en el
instante en que se ejecuta. No hay un valor intermedio en mis manos que pueda quedar obsoleto.

**Prueba de que hacen falta las dos:**

```python
lst[len(lst)-1]              # roto
if x not in lst: lst.append(x)   # roto
```

Cada pieza por separado es atómica (cumple la 1) y aun así están rotas: calculo un resultado
(`len`, `not in`) y lo uso después, cuando ya puede ser mentira. Es el contador otra vez con
otro disfraz. El patrón tiene nombre: **check-then-act**.

Consecuencia: `append` seguro **no** implica "las listas son thread-safe". Implica que *esa
operación* lo es.

### Lista vs. `queue.Queue`

| | lista + `append` | `queue.Queue` |
|---|---|---|
| seguridad | detalle de implementación de CPython, no está en la especificación del lenguaje | contrato documentado, lock explícito dentro |
| operaciones compuestas | las tendría que proteger yo | protegidas (sacar, bloquearse si vacía, tamaño máximo) |
| bloquear esperando trabajo | no | sí |
| tamaño máximo | no | sí (`maxsize`) |

Para recoger errores en un test, la lista vale y sobra. La cola de trabajos del **peldaño 3**
tiene que ser `Queue`, y el **peldaño 4** usa justo lo que la lista no da: `maxsize`.

---

## 6. Mecánica: `start` y `join`

```python
t = threading.Thread(target=fn, args=(...))   # lo crea, NO lo ejecuta
t.start()    # lo lanza y VUELVE INMEDIATAMENTE. No espera.
t.join()     # el hilo que ejecuta esta línea se para hasta que t termine
```

**El sujeto de `join` es quien llama, no el worker.** `t.join()` significa "yo, el hilo
principal, me quedo parado hasta que `t` termine". Al worker no se le ordena nada: lleva
corriendo desde el `start` y terminará cuando su función retorne, lo espere o no.

Sin `join` el hilo **no** corre infinito. Termina solo. Lo que falta sin `join` es *saber
cuándo*: el principal llegaría a los `assert` en microsegundos, midiendo un estado a medias,
con un número distinto en cada ejecución.

> `start()` es "vete a hacer esto". `join()` es "yo me quedo aquí hasta que vuelvas".

### Por qué dos bucles separados

```python
for t in hilos: t.start()    # todos vivos a la vez
for t in hilos: t.join()     # esperar a todos
```

```
t1  ████████
t2  ███████████
t3  █████████
    ↑ solapados. Duración total ≈ el más lento.
```

Frente a la versión mala:

```python
for t in hilos: t.start(); t.join()   # MAL
```

```
t1  ████████
t2          ███████████
t3                     █████████
    ↑ nunca hay dos vivos. Duración = la suma.
```

`start t2` no se ejecuta hasta que t1 termina, porque el `join t1` anterior tiene bloqueado al
hilo principal — y quien lanza los hilos **es** el principal. Si está parado, no lanza nada.
Resultado: un worker vivo en todo momento → ejecución **secuencial** → el caso correcto →
el test no mide nada.

Esperar a los tres uno detrás de otro **no** hace que trabajen uno detrás de otro.
(Analogía: mandas a tres a hacer recados, te pones en la puerta a recogerlos. Han estado los
tres en la calle todo el rato.)

### Otras trampas

- `t.run()` o llamar a `fn()` directo → se ejecuta en el hilo principal. Cero concurrencia,
  test verde y vacío.
- **Una excepción dentro de un hilo no sale de ese hilo.** No propaga al principal, pytest no
  la ve, el test pasa. Si los N workers revientan en el primer POST, la aserción final compara
  0 con 0 y da verde. → cada worker captura y guarda el error en una estructura compartida.
- Concurrencia en el cliente ≠ concurrencia en el servidor. Con `HTTPServer`, 20 hilos de
  cliente se atienden de uno en uno. El cambio a `ThreadingHTTPServer` en el fixture es lo que
  hace que el test signifique algo.

---

## 7. Diseño de tests de carga

**Un test sin `assert` no es un test.** Verde vacío ≠ verde informativo. Si el servidor
devolviera 500 en las 3.000, saldría igual de verde.

**Las tres aserciones del test de estrés:**
1. la lista de fallos, vacía → ataca "¿reventó algo?"
2. todos los status a 201 → ataca "¿respondió bien?"
3. `len({ids devueltos}) == N*M` → ataca la **avería (b)**, y es la razón de ser del test

Los ids que importan son **los que devuelve el servidor en el cuerpo**, no los índices `i` de
mis bucles.

**Con N resultados no afirmas N veces: agregas y afirmas una.**

```python
for r in results: assert r['status'] == 201      # MAL
assert {r['status'] for r in results} == {201}   # BIEN
```

El bucle corta en el primer fallo y siempre da el mismo mensaje. No distingue 1 fallo de
3.000 de 1.500 de 3.000 — que son diagnósticos opuestos: uno es una race que salta rara vez,
el otro es un servidor roto de base. Ni distingue si apareció un código distinto o varios.
El `set` imprime `assert {201, 500} == {201}` en una línea. `collections.Counter` da además
las cantidades: `{201: 2987, 500: 13}`.

**No afirmar sobre el interior de los elementos de una lista que esperas vacía.** Mina:

```python
assert len({f['data']['id'] for f in failures}) == 0
```

En los fallos `data` es `None` → `None['id']` → `TypeError`. Hoy pasa porque `failures` está
vacía y el cuerpo no se evalúa. El día que haya un fallo, el test no dirá "hubo 1 fallo":
petará con un `TypeError` dentro de la propia aserción.

**El almacén tiene que venir limpio.** Con `scope="module"` todos los tests comparten el
mismo servidor y el mismo `RawData`. Si otro test creó un job antes, no se puede afirmar
`len(jobs) == N*M` y el número depende del orden de ejecución de pytest. Un test de estrés
que afirma sobre estado global necesita su propio servidor.

**Escala: que dure décimas de segundo, no un minuto.** Medido:

| carga | peticiones | tiempo |
|---|---|---|
| 100 hilos × 1000 | 100.000 | 58 s |
| 15 hilos × 200 | 3.000 | 2,9 s |

Sobre este test se itera muchas veces (instrumentar, meter el lock, volver a correr). Un
minuto por vuelta es inaceptable. El número grande, al final.

Dato para el **peldaño 7**: esos 58 s de reloj consumieron ~73 s de CPU repartidos entre 100
hilos. No se usaron 100 núcleos.

---

## 8. Paso 4 — reproducir la race: el sitio del corte decide la avería

La instrumentación: `RawData(yield_point=lambda: time.sleep(0))`, y en `save()` un
`if self.yield_point: self.yield_point()` en el punto crítico.

`time.sleep(0)` cede el turno —suelta el GIL, el planificador puede dar paso a otro— y pide
cero espera: el hilo queda inmediatamente listo otra vez. Es el bostezo mínimo.
`sleep(0.001)` también serviría y haría la race **más** fiable (ventana de 1 ms en vez de
microsegundos), pero cuesta tiempo, y con el lock puesto esa siesta se serializa.

### Resultados medidos (15 hilos × 200 POSTs = 3.000)

| cesión | `jobs` | `counter` | `ids_unicos` | avería |
|---|---|---|---|---|
| **sin** `yield_point` | 3000 | 3000 | 3000 | ninguna observable |
| entre lectura 1 y lectura 2 | **3000** | 3000 | ~2910 | **(b)** identidad corrupta, 0 perdidos |
| entre lectura 2 y el incremento | **~2900** | 3000 | ~2900 | **(a)** ~100 jobs perdidos |

Cinco corridas consecutivas con el corte abajo: 2919, 2884, 2920, 2907, 2872 ids únicos de
3.000. Reproducible.

### El modelo correcto del `yield_point`

**No protege nada. Es lo contrario de un lock.**

- Un **lock** impide que B entre. Protege.
- Un **yield** invita a B a entrar en el peor momento. Expone.

Es un **corte** en la ejecución de A. Parte `save()` en dos mitades: lo de arriba, A ya lo
hizo; lo de abajo, sigue sin hacer. B, al arrancar, **ve el mundo tal como A lo dejó en el
corte**.

De ahí se deriva todo:
- Corte **antes** de la lectura 2 → B copia un id caducado en su cuerpo, pero al insertar el
  contador ya avanzó → claves distintas, ids duplicados → **(b)**.
- Corte **después** de la lectura 2 → B usa el contador sin incrementar **como clave** →
  misma clave, uno pisa al otro → **(a)**.

> El sitio del corte **selecciona** qué avería reproduces. Una race con tres lecturas no
> tiene un modo de fallo, tiene varios. Un test que abre una sola ventana demuestra uno.

### Firma diagnóstica

- `counter == len(jobs)` y `ids_unicos < len(jobs)` → avería **(b)**
- `counter > len(jobs)` → avería **(a)**

En (a), `ids_unicos == len(jobs)` porque las inserciones con clave repetida colapsan: tres
cuerpos con el id 7 dejan una sola entrada, pero el contador se incrementó tres veces.
**`counter > len(jobs)` es la huella de la pérdida**, y se puede comprobar en el test mirando
el almacén por dentro, no a través de las respuestas.

### El error de predicción

Predije 2.500 supervivientes de 3.000 (17 % de daño). Real: ~2.900 (3 %). Mi modelo
sobreestimaba el daño por un factor de 6. El dato del bucle puro de Python (6,5 % de
supervivencia) lo subestimaba aún más en el otro sentido.

Motivo: los hilos pasan el 99 % del tiempo bloqueados en el socket, no dentro de `save()`.
La probabilidad de que dos coincidan en la sección crítica es baja. **La ventana existe; lo
que varía es cuántas veces se acierta en ella.**

---

## 9. Hallazgo colateral: el backlog de 5

Síntoma: `ConnectionResetError(104)` en 1-2 peticiones de 3.000, intermitente, **también sin
instrumentación**. Hacía fallar `assert len(failures) == 0` y **tapaba la aserción de ids**,
que era la que importaba.

No tiene nada que ver con hilos, ni con el contador, ni con la race.

Mecánica: cuando un cliente conecta, el kernel completa el saludo TCP él solo y aparca la
conexión en una cola. El servidor las saca con `accept()` (eso es el bucle de
`serve_forever`). Si la cola está llena, el kernel rechaza la nueva → RST → el cliente ve
"connection reset by peer".

El tamaño se fija al abrir el socket:

```python
# socketserver.TCPServer
def server_activate(self):
    self.socket.listen(self.request_queue_size)   # ← vale 5
```

`request_queue_size` es **atributo de clase**, y `server_activate()` corre dentro del
`__init__` → hay que fijarlo antes de construir → subclase:

```python
class JobServer(ThreadingHTTPServer):
    request_queue_size = 128
```

Escala: nginx usa 511; `/proc/sys/net/core/somaxconn` en esta máquina es 4096. El 5 de la
librería estándar es un default fósil.

**Causa de fondo, no arreglada:** `BaseHTTPRequestHandler.protocol_version` es `HTTP/1.0`,
sin keep-alive. Cada POST abre una conexión nueva: handshake de tres vías → petición →
respuesta → cierre, 3.000 veces. Eso es la mayor parte de los 580 µs por petición y lo que
provoca los picos que desbordan la cola. Subir el backlog tapa el síntoma.

### Lección de diseño de test

Un fallo de transporte intermitente en la **primera** aserción oculta el resultado que el test
existe para medir. Separar los ejes: "¿funcionó el transporte?" es una pregunta distinta de
"¿es correcto el almacén?". Y la aserción que define el contrato no debe ir detrás de una
aserción frágil.

---

## 10. Paso 5 — el lock

```python
from threading import Lock

class RawData:
    def __init__(self, yield_point=None):
        ...
        self.lock = Lock()
```

Resultado: tres corridas verdes **con el `yield_point` puesto**. Es la evidencia que cierra el
control: *incluso forzando el peor intercalado posible, el invariante aguanta.*

### Las tres reglas

**1. Atributo de instancia, no local del método.** Un `lock = Lock()` dentro de `save()` crea
un lock nuevo en cada llamada: cada hilo coge el suyo, ninguno espera a nadie, no protege
nada. Un lock solo sirve si **todos los hilos cogen el mismo objeto**. Lo que hace que el bug
exista —una única instancia compartida— es lo que hace que el lock funcione.

**2. El lock vive junto al estado que protege.** El estado compartido es `self.jobs` y
`self.counter`, y están en `RawData`. En `ServiceValidation` estaría protegiendo un dato
ajeno, y cualquiera que llame a `RawData` directamente se lo salta.

**3. `with self.lock:`, no `acquire()` / `release()`.** No es estilo, es corrección:

```python
self.lock.acquire()
...                      # si algo aquí lanza una excepción...
self.lock.release()      # ...esta línea NO se ejecuta
```

El lock queda cogido para siempre. Toda petición posterior se bloquea en la puerta y no sale
nunca: **el servidor se cuelga entero y de forma permanente**. No devuelve errores, no se
reinicia, deja de responder.

Y no es hipotético: pasó en una sonda de esta misma sesión. Un `yield_point` con la firma
equivocada lanzaba `TypeError` justo entre el `acquire` y el `release`. Sin lock, el resultado
fueron 3.000 peticiones fallidas —ruidoso, evidente, diagnosticable—. Con lock y
`acquire`/`release` a mano, el mismo fallo habría dejado el servidor muerto en silencio en la
primera petición.

`with` libera el lock aunque el cuerpo lance. Es `try/finally` escrito en una línea.

### El coste

Un lock es **serialización deliberada**: convierte un tramo concurrente en una fila india. Por
eso se pone en el trozo más pequeño posible.

Predicción a contrastar: como la sección crítica son tres operaciones de dict (nanosegundos),
el lock no cambia el tiempo de forma medible —2,3 s antes, 2,3 s después— porque el ruido de
la red lo tapa. En el peldaño 7, con el endpoint lento, pasará lo contrario.

---

## 11. La frontera del almacén: quién es dueño de cada objeto

El lock protege el estado **mientras está dentro**. No sirve de nada si el estado sale o entra
por la puerta.

> Un lock solo funciona si **todos** los accesos al estado protegido pasan por él.
> Y si todos deben pasar por él, el estado **no puede salir del objeto**. Lo que sale es copia.

### Las dos direcciones de la fuga

**Salida.** `return self.jobs[id]` entrega una referencia al objeto guardado. Quien la recibe
puede mutarlo sin lock y sin enterarse. Cuatro de los cinco métodos lo hacían: `save`, `get`,
`get_all` y `update`. `delete` era el único limpio, y por un motivo concreto: el objeto que
devuelve **ya salió del almacén**, nadie puede alcanzarlo, no hay nada que proteger.

**Entrada.** La que no se ve:

```python
data = json.loads(body)          # dict del handler
...
self.jobs[id] = data             # el almacén ADOPTA el objeto del handler
```

`self.jobs[id] = data` no copia: guarda una **referencia**. Después de esa línea, la variable
del handler y `self.jobs[id]` son el mismo objeto con dos nombres.

Copiar en el `return` no tapa esto: el handler ya tenía el objeto **antes** de llamar.

### Una sola copia, en la entrada

```python
def save(self, data):
    with self.lock:
        data['id'] = self.counter
        self.jobs[self.counter] = data.copy()   # ← la única copia
        self.counter += 1
    return data                                  # el objeto del handler, que ya era suyo
```

Objetos que existen al terminar: `data` (dueño: el handler) y la copia (dueño: el almacén).
Cada uno con un único dueño → frontera cerrada. Un `return data.copy()` crearía un tercero
idéntico al primero para dárselo a quien ya lo tiene.

> Criterio, sin intuición: **cuenta los objetos y quién puede alcanzar cada uno.** Si un objeto
> tiene dos dueños que pueden escribirlo, la frontera está rota.

### Superficial, dos niveles o profunda

| | coste (3.000 jobs) | |
|---|---|---|
| un solo job, `.copy()` | **0,033 µs** | 33 ns: gratis |
| `jobs.copy()` | 14 µs | solo el mapa, valores compartidos → **insuficiente** |
| `{k: v.copy() ...}` | **163 µs** | frontera completa con valores planos |
| `deepcopy(jobs)` | 3.540 µs | 22× más, protección idéntica → **descartado** |

`deepcopy` solo gana con anidamiento real. Hoy los jobs tienen un nivel y valores inmutables.
Llegará su día: cuando `result` deje de ser `None` y contenga una lista o un dict, la
comprensión de dos niveles deja de bastar.

Los 163 µs se pagan **con el lock cogido**, bloqueando a todos los escritores: el 28 % de lo
que dura una petición. Hoy da igual porque casi no hay GETs. Si `get_all` se volviera
frecuente, el arreglo es copiar el mapa dentro del lock y los valores fuera.

### Qué va dentro del lock

**El intervalo que debe ser indivisible, ni una línea más.** Un lock es serialización: todo lo
que metas dentro bloquea a los demás.

- `save`: el RMW completo. El `return data.copy()` fuera — `data` es del hilo.
- `get` / `get_all`: el acceso a `self.jobs`, comprensión incluida. El `return` dentro del
  `with` es correcto: `__exit__` corre en cualquier salida, también por `return`.
- `update` / `delete`: del `if` hasta la escritura. Es check-then-act, y es indivisible.

Y `with self.lock:`, nunca `acquire()` / `release()` a mano: si algo lanza entre medias, el
lock queda cogido para siempre y **el servidor se cuelga entero, en silencio**.

### El `None` defensivo que escondía el bug

```python
self.jobs.pop(id, None)    # antes
self.jobs.pop(id)          # ahora
```

Con el `if` de arriba, el `pop` no puede fallar. Ese `None` solo servía para silenciar el caso
en que la garantía era falsa — que es justo el caso que quieres ver. Dos DELETE simultáneos
pasaban los dos el check, el segundo recibía `None`, y el handler respondía 204 a ambos.

> No pongas un valor por defecto defensivo para tapar un estado imposible. Si de verdad es
> imposible, que reviente cuando deje de serlo.

### `Lock` no es reentrante

Si un método cogiera el lock y llamara a otro que también lo coge, **el hilo se espera a sí
mismo**. El lock no guarda quién lo tiene: solo "cogido / libre". Para él la petición del
propio dueño es indistinguible de la de un extraño, y la trata igual: a esperar.

No lanza, no hay timeout, no muere. El hilo queda vivo, parado, **y con el lock cogido** → se
bloquean todos los demás. El servidor deja de responder sin un solo mensaje de error. Eso es
un **deadlock**.

`RLock` lleva la cuenta del hilo dueño y permite reentrar. Pero necesitarlo suele indicar que
no está claro qué capa es dueña de la sección crítica. Estructura limpia: métodos internos sin
lock, y el lock se coge una vez en el método público.

Hoy ningún método llama a otro. La tentación llega en el peldaño 3, con los workers.

---

## 12. Los tests de encapsulación, y cómo saber si un test sirve

Tres tests unitarios de `RawData` — sin servidor, sin HTTP. Por HTTP no probarían nada: el
JSON que recibe el cliente ya es una copia por definición.

Cada uno muta algo y comprueba el almacén **a través de la propia API**, nunca mirando
`self.jobs`. Un test que hurga en los atributos internos queda atado a la implementación y se
rompe al meter SQLite en el peldaño 7.

```python
job = storage.get(id)
job["payload"] = "MUTATED"
assert storage.get(id)["payload"] == "test_load"    # el segundo get es la ventana
```

Dos errores que cometí escribiéndolos:

**`assert job != job2`.** Dice "son distintos". Pasaría también si `get` devolviera basura.
Hay que afirmar **el valor esperado**, no una diferencia.

**El valor esperado recalculado a partir del id.** `assert jobs2[k]["payload"] == f"test_load{k}"`
solo funciona mientras clave e índice coincidan — la suposición que precisamente quería
eliminar. El esperado tiene que venir de lo que registré al crear:

```python
expected[job["id"]] = f"test_load{i}"
```

Así el test no sabe ni le importa qué ids genera el almacén.

Nota sobre `save`: devuelve el **mismo objeto** que se le pasó, así que mutar el retorno y
mutar la entrada son la misma operación. Una sola frontera que probar, no dos.

### Mutation testing

Introducir a propósito el bug que el test dice prevenir, y comprobar que lo caza.

```
save adoptando el objeto   -> rojo en test_inmutability_save
get devolviendo referencia -> rojo en test_inmutability_get
get_all superficial        -> rojo en test_inmutability_get_all
```

Cada mutante detectado por exactamente un test. Sin solapes (el test apunta a una sola
frontera) y sin huecos (ningún mutante sobrevive).

Es la forma general de lo que hice a mano con el `yield_point`:

> **Un verde solo significa algo si antes supe producir el rojo.**

Si al romper una línea no se pone rojo ninguno, el test es decorativo. Si se pone rojo otro
distinto del que esperaba, los tests no vigilan lo que creo que vigilan.

---

## 13. Estado del peldaño 1 — CERRADO

- [x] `ThreadingHTTPServer` en `run()` y en el fixture de concurrencia
- [x] Papel: trazas (a) y (b)
- [x] Test de estrés con aserciones reales
- [x] `JobServer` con `request_queue_size = 128` → fuera el rojo de transporte
- [x] Paso 4: `yield_point` → **rojo**, 2.872–2.920 ids únicos de 3.000, reproducible
- [x] Paso 5: lock → **verde** con la instrumentación puesta
- [x] `with self.lock:` en los cinco métodos
- [x] Copias en la frontera: una, en la entrada de `save` y `update`; al salir en `get`/`get_all`
- [x] `pop(id)` sin el `None` defensivo
- [x] Invariante escrita en el docstring de `RawData`
- [x] Tres tests de encapsulación, verificados por mutación
- [x] Commit

**Verificación final** (sonda externa, 4 escritores concurrentes `save`+`update`+`delete`
contra 500 `get_all` y 20.000 `get`): cero errores en lectores y escritores, y las tres
fronteras intactas. Suite: 9 passed.

### Decisión de diseño, escrita a propósito

- `test_integration.py` → `HTTPServer`. Valida semántica: rutas, códigos, CRUD. **Secuencial
  a propósito**: si falla, es el routing, no un artefacto de concurrencia.
- `test_concurrency.py` → `JobServer`. Valida el almacén bajo carga. **Concurrente a
  propósito.**
- `test_raw_data.py` → sin servidor. Valida las fronteras del almacén.

---

## 14. Preguntas abiertas

Respondidas en esta sesión: qué suelta el GIL (E/S y dormir), por qué `append` es segura,
cómo instrumentar sin duplicar código.

Pendientes:

1. ¿Qué debería responder la API a un `POST /jobs/5`? Comparar con cómo se trata el id en
   `do_PUT` y `do_DELETE`. Ahora responde 201 y se inventa el id, porque el router solo mira
   `parts_url[1]`.
2. ¿Por qué `get_all()` devolviendo el dict interno pasa de "feo" a "fallo" al meter hilos?
3. `update` hace `if id not in self.jobs` y luego escribe. ¿Qué patrón es eso? (Ya tiene
   nombre en la sección 5.) ¿Basta con un lock por método?
4. `ThreadingHTTPServer`: ¿cuántos hilos puede llegar a crear? ¿quién los destruye?
   (Relevante en el peldaño 4.)
5. Si `save()` coge el lock y `get_all()` también, ¿un GET bajo carga de POSTs se ralentiza?
   ¿Cómo lo mediría?

---

## 15. Vocabulario

| término | definición operativa |
|---|---|
| **race condition** | el resultado depende del orden de ejecución, y ese orden no lo controlo yo |
| **lost update** | dos hilos leen el mismo valor antes de que ninguno escriba; la segunda escritura pisa a la primera sin haberla visto |
| **read-modify-write** | leer, calcular a partir de lo leído, escribir. Tres pasos, dos huecos |
| **check-then-act** | comprobar una condición y actuar según ella; entre medias deja de ser cierta |
| **sección crítica** | el intervalo entre la lectura y la escritura. No un instante: un intervalo |
| **punto de cesión** | lugar donde el intérprete puede cambiar de hilo (E/S, espera, punto de control) |
| **corte** | lo que hace el `yield_point`: parte el método en dos y deja entrar al otro hilo en medio |
| **atómico** | se ejecuta como una unidad; nadie observa el estado intermedio |
| **estado compartido** | alcanzable desde más de un hilo. Lo único que necesita protección |
| **barrera de sincronización** | punto a partir del cual se puede afirmar que el trabajo está hecho (`join`) |
| **serializable** | un schedule concurrente es correcto si equivale a alguna ejecución secuencial |
| **backlog** | cola del kernel con las conexiones aceptadas por TCP pero no recogidas aún por `accept()` |

---

## Apéndice: errores que cometí, para no repetirlos

1. Leer dos columnas de una traza como "dos colas de peticiones". Son **hilos**; las filas
   son **tiempo**. Una fila = un paso, ejecutado por un solo hilo.
2. Creer que "secuencialmente" describía el caso roto. Secuencial = correcto. Solapado = roto.
3. Fusionar mentalmente `data['id']` y la clave del dict. Son dos lecturas distintas de
   `self.counter` en dos momentos distintos.
4. Leer `t1.join()` como una orden al worker. El sujeto es quien llama.
5. Pensar que la lista era segura por ser "modificada por hilo". Es igual de compartida que
   el contador; lo que la salva es *cómo* se actualiza.
6. Confundir mutabilidad con compartición. `self.counter` es un `int` **inmutable** y es el
   que revienta.
7. Escribir un test sin `assert` y leer el verde como éxito.
8. Invertir el filtro: `if error is None` recoge los éxitos, no los fallos.
9. `for i in range(200)` dentro de una función cuyo parámetro ya se llamaba `i` (shadowing).
10. Agregar con un `set` **y** dejar el bucle alrededor: la misma expresión evaluada 3.000
    veces.
11. Afirmar sobre el interior de los elementos de una lista que espero vacía:
    `failure['data']['id']` con `data = None` → `TypeError` dentro de la propia aserción.
12. Pasar `time.sleep` pelada como gancho y llamarla `self.yield_point(0)`. El `0` pertenece
    al test; el código de producción no debe saber qué hay dentro del gancho.
13. Predecir que mover la cesión una línea abajo sería inofensivo "porque los datos ya están
    cogidos". En concurrencia, "ya está cogido" no significa nada: hay que preguntar **a
    salvo de qué**.
14. Llamar "barrera" al `yield_point` y hablar de estar "protegido" dentro. Es lo contrario:
    un lock protege, un yield expone.
15. Ignorar dos avisos sobre el `ConnectionResetError` y seguir leyendo el rojo equivocado
    durante tres corridas.
16. No distinguir qué aserción estaba fallando (`== 0` vs `== 3000`). Leer el mensaje de
    error completo, no el hecho de que haya rojo.

---

## Hilo conductor, en una frase por paso

1. Meter hilos no crea el bug: lo **expone**. El bug es el estado compartido sin protección.
2. El papel demuestra que el intercalado malo **existe**. Es una prueba de existencia.
3. El GIL hace que ese intercalado no sea **realizable** en este código: no hay punto de
   cesión en la sección crítica. Correcto ≠ "no falla hoy".
4. El `yield_point` crea el punto de cesión y lo hace realizable. El **sitio del corte**
   decide qué avería sale.
5. El lock elimina los intercalados malos **por construcción**, no por suerte del
   planificador.
6. El verde solo vale **con la instrumentación puesta**. Sin ella, el verde ya salía con el
   código roto.
