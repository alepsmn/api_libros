# Peldaño 2 — El endpoint lento bajo carga

Continúa [concurrencia.md](concurrencia.md), que cubre el peldaño 1.

---

## 1. Por qué este peldaño

El benchmark del peldaño 1 no medía el servidor: medía la tubería vacía. 580 µs por
petición de los cuales la lógica propia era menos del 1 % — el resto es socket, hilo del SO,
parseo HTTP y serialización.

Hasta que el trabajo pese más que la maquinaria, ningún número significa nada.

**Qué se construye:** que procesar un job cueste tiempo de verdad, **dentro del handler**, de
forma síncrona. El POST no responde hasta que el trabajo está hecho. Sin colas — eso es el
peldaño 3, y existe precisamente porque esto se rompe.

---

## 2. Los dos arquetipos de lentitud

Toda operación real cae en una de estas dos casillas, y de eso depende si añadir hilos sirve
de algo:

| **suelta el GIL** (espera) | **lo retiene** (cálculo en Python puro) |
|---|---|
| consulta a BBDD | parsear JSON grande |
| llamada HTTP a otro servicio | tokenizar texto |
| leer o escribir un fichero | recorrer y transformar listas |
| `time.sleep` | serializar a mano |

> La habilidad que se entrena no es escribir bucles: es **saber en qué casilla cae cada
> operación del sistema**.

**Precisión importante:** "intensivo en CPU" no implica "retiene el GIL". Muchas extensiones
en C lo sueltan mientras calculan — numpy, torch, `hashlib` con entradas grandes, compresión.
Por eso en Python funciona la receta de "mete el bucle caliente en C": no solo va más rápido,
además deja de bloquear a los demás hilos.

### Por qué carga sintética y no trabajo real

Con trabajo real **no se puede barrer el parámetro**. Si la operación tarda lo que tarda, no
se puede medir la curva a 10, 50, 200 ms y ver dónde cambia el comportamiento. Es lo que
hacen `wrk`, `fio`, `stress-ng` y los benchmarks de serving, que miden con prompts sintéticos
de N tokens exactos.

---

## 3. El modelo: qué predecir antes de medir

**Montaje:** N clientes lanzando peticiones una detrás de otra. Cada petición cuesta T
segundos de trabajo.

**Caso espera (suelta el GIL).** Los N hilos duermen a la vez; los T segundos de uno se
solapan enteros con los de los demás.

```
throughput ≈ N / T          latencia ≈ T
N=16, T=0,1  →  160 req/s   latencia 100 ms
```

**Caso cálculo (retiene el GIL).** Solo un hilo ejecuta bytecode en cada instante. Los T
segundos de cada uno no se solapan con nada.

```
throughput ≈ 1 / T          latencia ≈ N × T
N=16, T=0,1  →  10 req/s    latencia 1,6 s
```

> **La conclusión que tiene que doler:** en el caso de cálculo, añadir clientes **no añade
> throughput**. Solo añade latencia. De 10 req/s con 1 cliente a 10 req/s con 64, pero la
> latencia ×64.

### Ley de Little

```
clientes = throughput × latencia
```

`16 = 160 × 0,1` ✓   `16 = 10 × 1,6` ✓

Las dos salen. De las tres magnitudes solo se pueden elegir dos.

### Confirmación accidental

La suite de concurrencia con `ms = 100` tardó **21,9 s**: 15 hilos × 200 peticiones × 100 ms
de espera.

```
medido:    3000 / 20 s = 150 req/s
predicho:  N / T = 15 / 0,1 = 150 req/s
Little:    15 = 150 × 0,1  ✓
```

Clavado. La curva de espera se comporta exactamente como el modelo. Falta la otra.

---

## 4. La carga sintética

```python
def waiting(ms):      time.sleep(ms / 1000)
def calculating(ms):  end = time.thread_time() + ms / 1000
                      while time.thread_time() < end: pass
```

### El reloj: la decisión que hace que el experimento mida algo

Para quemar CPU no hay que buscar una operación que dure exactamente eso: se gira en un bucle
hasta que el reloj diga basta. Pero **qué reloj** lo decide todo.

`perf_counter()` mide **tiempo de pared**. Con 16 hilos turnándose el GIL, cada uno recibe
~1/16 del CPU: si el bucle sale a los 100 ms de pared, ese hilo solo ha hecho ~6 ms de
trabajo real, y la curva de cálculo saldría idéntica a la de espera. El experimento no
mediría nada.

`thread_time()` mide **tiempo de CPU de ese hilo**. Es el correcto.

Verificación: con un cliente, los dos relojes coinciden y las dos funciones tardan lo que
dicen. La diferencia aparece bajo carga — `calculating(100)` seguirá consumiendo 100 ms de
CPU pero tardará mucho más de 100 ms de reloj.

### Unidades

Todos los relojes del módulo `time` devuelven **segundos en coma flotante**, `thread_time()`
incluido. El campo se llama `ms`, así que la conversión va dentro de la función.

Error cometido: `time.sleep(ms)` con `ms = 100` duerme 100 **segundos**. La suite de
concurrencia (3.000 peticiones) habría terminado en unas seis horas.

> Un trabajo que no dura lo que crees invalida todas las mediciones del peldaño. Cronometrar
> cada función por separado, con un solo cliente, **antes** de montar nada encima.

---

## 5. El contrato del job cambia

`payload` deja de ser una cadena decorativa y pasa a ser lo que siempre debió ser: **la
descripción del trabajo a hacer**.

```python
{"payload": "tarea_prueba"}                      # antes
{"payload": {"type": "wait",      "ms": 100}}    # ahora
{"payload": {"type": "calculate", "ms": 100}}
```

Por qué va en el job y no en un parámetro del servidor:
- Un solo servidor corriendo: se mide espera, se mide cálculo, se compara, sin reiniciar.
- El arnés decide qué manda; el servidor no sabe nada del experimento.
- Se pueden mezclar tipos en la misma tanda — medición interesante por sí sola.
- Y sobre todo: **es lo que un job es de verdad.** En el peldaño 3 el worker cogerá el job de
  la cola y leerá ese `payload` para saber qué ejecutar.

Un dict **es** un objeto: "objeto" en JSON = `{...}` = `dict` en Python tras `json.loads`.
(Opción apuntada para más adelante: convertirlo en una instancia de clase ya validada en la
frontera — *"parse, don't validate"*. Hoy no.)

### Un cambio de contrato toca todas las capas

Cambiar la forma del dato rompe todo lo que lo toca. No es señal de ir mal: es lo que es. Se
hace en orden, verificando cada paso:

1. el import
2. las unidades, sin servidor ni tests, con cronómetro
3. la forma nueva en los tests → suite verde → **commit**
4. la validación del contenido del payload
5. la profundidad de la copia
6. el despachador y el ciclo de vida

### Dónde vive cada responsabilidad

- `RawData` **guarda** jobs. No los ejecuta. El `payload` le es opaco.
- `ServiceValidation` **valida**. Ejecutar tampoco es validar.
- `processor.py` **ejecuta**. Responsabilidad nueva, sitio nuevo.

Si la ejecución se incrusta en una capa que ya tiene otra responsabilidad, en el peldaño 3 no
se podrá mover detrás de una cola.

Y si lo lento acabara dentro de `RawData`, correría **dentro del lock**: un trabajo de 100 ms
con el lock cogido serializa el servidor entero. Medible, y vale la pena medirlo como
contraste.

### Validación: va con la escritura, no con el endpoint que ejecuta

`POST` ejecuta; `PUT` no. Pero los dos **escriben** un job, así que los dos exigen la misma
forma de `payload`.

Si `POST` exige el objeto y `PUT` acepta una cadena, el almacén acaba con dos formas y la
validación depende de por qué puerta entró el dato. En el peldaño 3, un worker coge jobs sin
preguntar por dónde entraron: uno con una cadena en el `payload` revienta lejos, tarde, y sin
relación aparente con el PUT que lo causó.

`payload` presente ya no es contrato suficiente. Ahora es: *objeto, con `type` de una lista
cerrada y `ms` numérico y positivo*. Un `type` desconocido hoy no entra en ningún `elif`: no
ejecuta nada, no lanza nada, y responde **201** como si hubiera trabajado. Eso es un 400.

---

## 6. Test ≠ arnés

| | **test** | **arnés / benchmark** |
|---|---|---|
| produce | verde o rojo | números |
| se corre | en cada cambio | a propósito, cuando quieres datos |
| debe ser | rápido y determinista | lento está bien, es su trabajo |
| el resultado | es una respuesta | hay que interpretarlo |

Por qué no se mezclan:

- Metiendo la medición en pytest se pagan 20 s cada vez que quieres comprobar otra cosa.
- Y tienta afirmar sobre tiempos (`assert duracion < 0.5`). Eso hace el test **flaky**: falla
  porque el portátil estaba compilando, no porque el código esté mal. Un test que falla por
  motivos ajenos se acaba ignorando, y entonces ya no vigila nada.

`tests/test_concurrency.py` → rápido (`ms: 0`), afirma el invariante de la race.
`bench/carga.py` → fuera de `tests/`, sin `assert`, imprime una tabla.

---

## 7. Criterio de control del peldaño 2

1. **Las dos curvas medidas**: throughput y latencia para N = 1, 2, 4, 8, 16, 32, 64, con los
   dos tipos de carga.
2. **Una explicación escrita** de por qué son distintas que no diga "por el GIL" sin más:
   qué instrucción lo suelta, cuándo, y qué hace el planificador mientras.
3. **El punto donde se rompe**: subir la concurrencia hasta que algo ceda. Un hilo del SO por
   petición no es gratis. Hace falta el número y el síntoma.

### Medición extra que justifica el peldaño 3

Con N clientes martilleando POSTs lentos, lanzar en paralelo un cliente haciendo
`GET /jobs/0` —que cuesta microsegundos— y medir **su** latencia.

- Caso espera: no debería sufrir.
- Caso cálculo: sí. Un GET trivial pasando de 1 ms a cientos, esperando turno de GIL detrás de
  N hilos quemando CPU.

Un trabajo pesado degradando a todos los demás porque comparten un recurso. Es el argumento
entero del peldaño 3: sacar la ejecución del camino de la petición.

---

## 8. El planificador

El componente del kernel que decide **qué hilo corre, en qué núcleo y durante cuánto**. Hay
más hilos que núcleos, así que alguien reparte.

En CPython hay una segunda capa encima: aunque el kernel deje correr, solo se ejecuta
bytecode con el GIL en la mano. Un hilo que espera el GIL está listo para el kernel y parado
igualmente.

---

## 9. Consecuencia del cambio de contrato: la copia vuelve a quedarse corta

El job guardado ya no tiene valores planos:

```python
{"id": 7, "state": "pending", "result": None, "payload": {"type": "wait", "ms": 100}}
```

Y `get_all` hace:

```python
return {k: v.copy() for k, v in self.jobs.items()}
```

`v.copy()` es superficial sobre el job: copia las claves, pero el valor de `"payload"` sigue
siendo **el mismo dict** que hay en el almacén.

```python
todos[7]["payload"] = "otra cosa"     # NO llega al almacén (cambias la copia)
todos[7]["payload"]["ms"] = 999       # SÍ llega al almacén  ← frontera rota
```

Es lo que estaba previsto *"el día que `result` contenga un dict"*. Llegó antes, por `payload`.

**Y el test no lo caza.** `test_inmutability_get_all` hace `jobs[k]["payload"] = ...`:
reemplaza la clave en la copia, cosa que nunca llegaba al almacén. Pasa en verde con la
frontera rota.

> **Un test cubre exactamente lo que afirma, ni un milímetro más.** La forma de descubrirlo es
> la de siempre: romper la línea a propósito y ver si alguien se queja.

Pendiente: decidir la profundidad de copia que hace falta ahora y ampliar el test.

---

## 10. Estado

- [x] `processor.py` con `waiting` y `calculating`, unidades verificadas con cronómetro
- [x] `thread_time()` como reloj de la carga de cálculo
- [x] `payload` migrado a objeto en los dos tests → suite verde
- [x] `_check_payload_integrity` extraído; `val_update` valida pero no ejecuta
- [ ] Validar el **contenido** del payload: `type` cerrado, `ms` numérico positivo → 400
- [ ] `execute(payload)` en `processor.py` — el despachador, que el worker del peldaño 3 reutiliza
- [ ] Ciclo de vida: cuándo se guarda el job y con qué `state`. Hoy se guarda **después** de
      ejecutar, con `state: 'pending'` — el campo miente, y durante la ejecución el job no
      existe en el almacén
- [ ] Profundidad de copia en `get_all` + test que lo vigile
- [ ] `bench/carga.py` y las dos curvas

---

# MEDICIONES — resultados y lectura

Montaje: servidor en un proceso (`uv run python -m api_libros.server`), arnés en otro
(`bench/load.py`). Trabajo por petición T = 100 ms. Ventana de medición 5 s por punto.

---

## A. La tabla que resume el peldaño entero

Mismo servidor, mismo número de clientes (64), mismos 100 ms de trabajo por petición.
Lo **único** que cambia es si la operación suelta el GIL:

| | throughput | p50 |
|---|---|---|
| `wait` (suelta el GIL) | **620 req/s** | **102 ms** |
| `calculate` (lo retiene) | **10 req/s** | **6.084 ms** |

**62× menos throughput. 60× más latencia.** Esa es la diferencia entre las dos casillas de
la tabla de arquetipos, en números medidos.

Si solo me quedo con una cosa del peldaño 2, es esta.

---

## B. Curva `wait` — el trabajo se solapa

| N | predicho N/T | medido | % | p50 | p99 |
|---|---|---|---|---|---|
| 1 | 10 | 9,72 | 97% | 102,8 ms | 104,4 ms |
| 2 | 20 | 19,42 | 97% | 102,8 | 104,9 |
| 4 | 40 | 38,83 | 97% | 102,8 | 106,0 |
| 8 | 80 | 77,65 | 97% | 102,6 | 108,6 |
| 16 | 160 | 155,46 | 97% | 102,4 | 109,9 |
| 32 | 320 | 310,54 | 97% | 102,3 | 112,2 |
| 64 | 640 | 619,77 | 97% | 102,4 | 111,2 |

**Throughput lineal con N. Latencia plana.** 64 clientes simultáneos y ninguno espera a
ninguno: el `sleep` suelta el GIL y los 64 duermen a la vez.

### El 3 % que falta está medido, no es ruido

El déficit es **constante** en las siete filas → falta un término en el modelo. Y está a la
vista: `p50 = 102,8 ms`, no 100. Esos 2,8 ms son maquinaria: handshake TCP, parseo HTTP,
serialización JSON.

```
throughput = N / (T + c)        c ≈ 2,8 ms

1 / 0,1028 = 9,73    medido 9,72
64 / 0,1024 = 625    medido 620
```

> Un error **constante** no es ruido: es un término que falta. Un error **variable** sí suele
> ser ruido. Distinguirlos es la diferencia entre corregir el modelo y encogerse de hombros.

### El p99 se mueve antes que el p50

104 → 111 ms mientras la mediana no se entera. Primera señal de contención: creación de
hilos, GIL para parsear, cola de conexiones. Pequeño, pero es el fenómeno que domina el
peldaño 4.

---

## C. Curva `calculate` — el trabajo hace cola

| N | throughput | p50 | predicho N×T |
|---|---|---|---|
| 1 | 9,91 | 100,8 ms | 100 |
| 2 | 9,96 | 200,1 | 200 |
| 4 | 9,97 | 398,1 | 400 |
| 8 | 10,00 | 753,2 | 800 |
| 16 | 10,01 | 1.467,8 | 1.600 |
| 32 | 10,07 | 3.000,0 | 3.200 |
| 64 | 10,07 | 6.084,0 | 6.400 |

**Throughput plano en 10,0 req/s = 1/T, clavado en las siete filas.** De 1 a 64 clientes —×64
de carga— el servidor entrega exactamente lo mismo. Lo único que cambia es que cada cliente
espera 60 veces más.

> Con `calculate`, el servidor está **saturado con un solo cliente**. Cada cliente adicional
> no compra nada: solo hace cola.

Ese es el argumento del peldaño 3 en números.

### Dos detalles que no se ven de primeras

**El throughput es 10,07, ligeramente por encima de 10.** Si solo un hilo ejecuta bytecode,
¿cómo se hace más de un segundo de CPU por segundo? Porque mientras uno quema CPU con el GIL,
los otros hacen la parte que **no** lo necesita: sockets, llamadas al kernel. Eso sí va en
paralelo de verdad. Ni siquiera un servidor "limitado por el GIL" está serializado al 100 %.

**La cola explota.** p99/p50:

```
wait       N=64:  111 / 102  = 1,09
calculate  N=64: 9422 / 6084 = 1,55
```

El peor 1 % espera un 55 % más que la mediana. El GIL no se reparte por orden de llegada: no
hay cola justa, hay un relevo arbitrario, y algunas peticiones se quedan atrás repetidamente.

---

## D. El punto de ruptura (`wait`, N alto)

| N | predicho | medido | % | p50 | p99 |
|---|---|---|---|---|---|
| 128 | 1.245 | 1.234 | 99% | 101 ms | 134 ms |
| 256 | 2.490 | 2.440 | 98% | 101 ms | 127 ms |
| **512** | 4.980 | **2.180** | **44%** | 140 ms | **1.376 ms** |
| 1024 | 9.960 | 2.430 | 24% | 149 ms | 3.211 ms |

**La curva se dobla entre 256 y 512. El servidor satura en ~2.500 req/s.**

### La firma de la saturación, que es siempre la misma

1. el **throughput se aplana** — deja de crecer con N
2. la **latencia empieza a subir** — los clientes nuevos solo hacen cola
3. el **p99 explota primero**: 127 → 1.376 ms en un salto, con la mediana casi quieta

> La cola se entera mucho antes que la mediana. Vigilar el p50 es no enterarse de nada.

### Little da la media que no se midió

La ley usa la **media**, no la mediana:

```
latencia_media = N / throughput

N=256:   256 / 2440 = 105 ms     p50 101    ratio 1,03
N=512:   512 / 2180 = 235 ms     p50 140    ratio 1,68
N=1024: 1024 / 2430 = 421 ms     p50 149    ratio 2,82
```

Sin saturar, media ≈ mediana. Saturado, la media se va al triple. **Comparar media contra p50
dice si la distribución está sana, y es más barato que cualquier percentil.**

---

## E. ¿El límite es el servidor o el medidor?

Pregunta obligatoria en todo benchmark, y el error clásico: medir tu propio generador de
carga. El arnés son N hilos de Python en un proceso, parseando HTTP, **con un GIL**.

Comprobación: partir la carga en dos procesos y sumar.

```
1 proceso  × N=512      →  2.180 r/s     p50 140,1   p99 1376
2 procesos × N=256      →  1.306 + 1.205 = 2.510 r/s
                           p50 138,0   p99 1217
                           p50 138,3   p99 1325
```

**Veredicto: el límite es el servidor.** Partir el cliente compró un 15 %, no el doble.

Y la evidencia fuerte no es el throughput, son las latencias: **idénticas** en los dos
montajes. Los dos están en el mismo régimen saturado → chocan contra **la misma pared**. Si
la pared fuera el cliente, dos clientes habrían tenido dos paredes y la latencia habría
bajado.

Ese 15 % es el arnés contribuyendo algo al límite. Término secundario, pero real.

---

## F. Hallazgo: el GIL mata el `accept()`

A N=1024, mismo backlog (128), mismas conexiones simultáneas:

```
wait       →  0 errores
calculate  →  629 errores  [Errno 104] Connection reset by peer   (61 %)
```

¿Por qué rompe solo uno?

`Connection reset` significa que la cola de conexiones del kernel se desbordó, es decir que
**el servidor no llamaba a `accept()` lo bastante rápido**.

¿Y quién hace el `accept`? El hilo de `serve_forever`. Que es un hilo de Python. **Que
necesita el GIL.**

- En `wait`: los 1024 hilos duermen soltando el GIL → el hilo de accept lo coge cuando quiere
  y vacía la cola.
- En `calculate`: los 1024 hilos queman CPU con el GIL en la mano → el hilo de accept espera
  turno como todos → la cola de 128 se llena → RST.

> El trabajo pesado no solo frenó las peticiones: **impidió al servidor aceptar conexiones
> nuevas**. Un trabajo lento ahoga a todo lo que comparte su recurso, incluida la parte del
> servidor que no tiene nada que ver con él.

Y el síntoma secundario: el throughput **baja** (10,07 → 7,88). Si los errores fueran
rechazos baratos, el throughput aparente habría subido. Está pagando por fallar.

---

## G. Dos cosas que ningún error te habría contado

**Cero errores en las catorce filas de las curvas.** El servidor responde 201 a todo,
correctamente, mientras hace esperar **nueve segundos y medio** al peor cliente.

> Ningún código de error dice que un servidor es inútil. Solo la latencia. Mirando logs y
> contando 500s, todo iba perfecto.

Y la segunda: con `calculate`, el servidor ya estaba saturado **con un cliente**. No hubo
ningún punto en el que "empezara a ir mal". Iba mal desde el principio y la carga solo lo
hizo visible.

---

## H. Errores de medición cometidos (y cómo se detectan)

**1. Confundir las dos duraciones.** `ms` del payload = cuánto tarda el *trabajo* (la T del
modelo). El límite del bucle = cuánto dura la *medición*. Puse el trabajo a 5.000 ms con
ventana de 5 s → un hilo lanza una petición, vuelve a los 5 s, ve la ventana expirada y sale.
**Una muestra por hilo.**

*Síntoma:* p50 y p99 idénticos en casi todas las filas. Si coinciden, hay una sola muestra.

**2. Ventana menor que la latencia.** A N=256 con `calculate`, p50 = 20,9 s y ventana = 5 s.
Mismo efecto: una petición por hilo. Los percentiles dejan de ser sobre peticiones y pasan a
ser sobre hilos.

> La ventana tiene que ser **mucho mayor** que la latencia esperada, o no mides régimen
> estacionario: mides una sola ronda.

**3. Confundir la mediana con la media al aplicar Little.** `throughput × p50` salía al 35 %
de N y lo atribuí a muestras perdidas. Falso: en este arnés el `append` está **dentro** de la
iteración, y la condición del `while` solo se comprueba entre iteraciones — una petición que
arranca a los 4,9 s y vuelve a los 5,2 s se registra igual. **No se pierde ninguna muestra.**

Lo que faltaba era la métrica: **Little usa la media**. Con p50 = 149 ms y p99 = 3.211 ms, la
media está muy por encima de la mediana, y `N / throughput = 421 ms` **es** esa media.

*Lección:* antes de inventar un sesgo, comprobar si el modelo pide una magnitud distinta de la
que estoy midiendo.

**3-bis. El sesgo que sí existe: coordinated omission.** El arnés es de **lazo cerrado** —
cada hilo no manda la siguiente petición hasta que vuelve la anterior. Cuando el servidor va
lento, el cliente manda **menos** peticiones, justo en el peor momento. Un generador de lazo
abierto mantendría el ritmo pase lo que pase y vería un panorama peor. El sesgo es real; no es
que se descarten muestras, es que no se llegan a generar.

**4. Contaminar una tanda.** Lancé `wait` en paralelo sin querer durante una fila de
`calculate`.

> Un dato sucio **señalado** vale. Un dato sucio **mezclado** envenena la tabla entera.

**5. Medir la curva equivocada.** Busqué el punto de ruptura con `calculate`, que nunca pasa
de 10 r/s: eso estresa el **número** de hilos vivos, no el **ritmo** de creación de hilos y
conexiones. El techo de la maquinaria solo aparece con `wait`, a 2.500 r/s. Son dos límites
distintos.

**6. No agregar los errores por tipo.** "629 errores" no es un dato. `ConnectionReset`,
`timeout`, `RemoteDisconnected` y "no puedo crear más hilos" son cuatro averías con cuatro
causas y cuatro arreglos.

---

## I. Estado del criterio de control

- [x] **Las dos curvas medidas** — secciones B y C
- [x] **El punto de ruptura** — sección D: ~2.500 r/s entre N=256 y N=512, verificado que el
      límite es el servidor y no el medidor (sección E)
- [x] **El techo de la maquinaria** con `ms=0` — sección K: ~3.000 r/s
- [x] **El `GET` trivial bajo carga** — sección J: ×1 bajo `wait`, ×2.000 bajo `calculate`
- [ ] **La explicación escrita de las dos curvas**, que no diga "por el GIL" sin más: qué
      instrucción lo suelta, cuándo, y qué hace el planificador mientras
- [ ] Añadir la **media** al arnés, al lado del p50 (`N / throughput`)
- [ ] Etiquetar cada tanda con sus parámetros: una medición sin `type`, `ms` y N registrados
      no es una medición

### Transición al peldaño 3

- [ ] Validar el **contenido** del payload: `type` cerrado, `ms` numérico positivo → 400
- [ ] `execute(payload)` en `processor.py` — el despachador que reutilizará el worker
- [ ] Ciclo de vida: hoy el job se guarda **después** de ejecutar, con `state: 'pending'`. El
      campo miente, y durante la ejecución el job no existe en el almacén
- [ ] Refactor a dataclass congelado: si los jobs son inmutables, **las copias de la frontera
      desaparecen** (sección 9 y las del peldaño 1). Y el worker no podrá hacer
      `job['state'] = 'running'` — la invariante deja de depender de un comentario
- [ ] Paginación en `GET /jobs` (sección L)

## J. El `GET` trivial bajo carga — el resultado que cierra el peldaño

Montaje: servidor reiniciado, **un** job creado. `GET /jobs/0` en bucle desde **un** hilo, en
un proceso aparte. La carga de POSTs, en otro proceso, a **N fijo** (nada de barridos) durante
20 s; la ventana del GET son 10 s, arrancados ~3 s después, para medir solo el tramo estable.

```
                              GET /jobs/0              POSTs simultáneos
reposo                 2.750 r/s   p50   0,4 ms        —
bajo wait N=16         2.636 r/s   p50   0,4 ms        157 r/s   p50   101 ms
bajo calculate N=16        1,3 r/s p50 782,2 ms         10 r/s   p50 1.471 ms
```

**Bajo `wait`: cero degradación.** 0,4 ms vacío, 0,4 ms con 16 clientes en marcha.
**Bajo `calculate`: ×2.000.** De 0,4 ms a 782 ms.

Misma concurrencia, mismo trabajo por petición, mismo endpoint trivial. Lo único distinto es
si los otros hilos sueltan el GIL.

(Las filas de POST reproducen las del barrido del día anterior: 157 vs 155, 10,02 vs 10,01,
p50 1.470,7 vs 1.467,8. Las mediciones son reproducibles.)

### Por qué ×2.000 y no ×200: recuperar el GIL, no soltarlo

El GET necesita microsegundos de CPU. ¿Cómo acaba esperando 782 ms? Porque **no espera una
vez, espera varias**:

```
leer del socket        → suelta el GIL ... y tiene que volver a pedirlo
parsear la cabecera    → necesita el GIL
leer el cuerpo         → suelta ... y vuelve a pedirlo
buscar en el almacén   → necesita el GIL
serializar el JSON     → necesita el GIL
escribir al socket     → suelta ... y vuelve a pedirlo
```

Cada frontera de E/S lo devuelve **al final de la cola**, detrás de 16 hilos que quieren el
GIL para quemar CPU. Cinco fronteras = cinco esperas completas.

> Soltar el GIL es gratis. **Recuperarlo es lo que cuesta.**

De ahí la conclusión contraintuitiva: bajo carga de CPU, **la petición que más sufre es la
que más E/S hace**, aunque sea la que menos CPU necesita.

Es el mismo fenómeno del hallazgo F (el `accept()` ahogado), medido con precisión.

### Corrección de la predicción

Predije *"bajo `wait` casi no sufre, porque los hilos duermen soltando el GIL"*. La primera
tanda —con `wait` y `ms=0`— degradó el GET ×49, y parecía contradecirlo.

No lo contradecía: `wait` con `ms=0` **satura** (3.000 r/s = el techo), mientras que `wait`
con `ms=100` deja el servidor al 20 % de su capacidad. El nombre de la carga no es lo que
importa.

> Lo que decide si una petición trivial sufre no es qué tipo de trabajo hacen las demás:
> es **si al servidor le queda capacidad libre**. Soltar el GIL solo ayuda cuando hay hueco.

### Lo que cierra

Con `calculate`, el servidor no ofrece **ninguna** garantía de latencia sobre **ninguna**
petición. Leer un dict y serializarlo tarda 782 ms porque alguien, en otra conexión, está
haciendo cuentas. Respondiendo 200 a todo y con cero errores.

---

## K. El techo de la maquinaria (`ms = 0`)

```
N=1    2.600 r/s    p50  0,4 ms
N=2    2.900 r/s    p50  0,7 ms
N=64   3.140 r/s    p50 20,3 ms
```

**Techo ~3.000 r/s, alcanzado ya con N=2.** De 2 a 64 el throughput no se mueve; la latencia
crece lineal con N (0,4 → 0,7 → 1,3 → 2,5 → 5,0 → 10,0 → 20,3).

Esa forma —throughput plano, latencia proporcional a N— **es la curva de `calculate`**. Con
cero trabajo.

Porque el servidor sin hacer nada también ejecuta bytecode: parsear HTTP, construir el
handler, validar, serializar JSON. **La maquinaria de cada petición está serializada por el
GIL igual que el trabajo.**

```
1 / 3.100 = 0,32 ms de trabajo serializado por petición
comprobación: 64 × 0,32 = 20,5 ms      medido 20,3 ms
```

Little, con estos datos: `3.142 × 0,0203 = 63,8` contra N=64. Clavado, sin cola
(p99/p50 = 1,09): saturación limpia y reparto justo.

Comparación de techos:

```
ms = 0     →  ~3.000 r/s
ms = 100   →  ~2.500 r/s  (wait)
```

**El trabajo no era el cuello de botella: la tubería sí.** Y el 17 % que cuesta el `sleep` no
es CPU —no consume— sino cientos de hilos más vivos: memoria, cambios de contexto,
planificador. Nada es gratis.

### Qué significa el techo, y qué NO significa

Es el techo de **este código en esta máquina**. No es una propiedad de Python ni de HTTP: es
lo que cuesta este camino de petición concreto.

Y **el peldaño 3 no lo sube.** Las palancas para subirlo están todas en el camino de la
petición:

- **keep-alive** — hoy se abre y cierra una conexión TCP por petición (`protocol_version` es
  HTTP/1.0)
- **pool de hilos** en vez de hilo por petición — hoy se crean y destruyen 3.000 hilos del SO
  por segundo
- un **parser de HTTP** que no sea Python puro

Lo que hace el peldaño 3 es otra cosa:

```
techo real:        3.000 r/s
calculate hoy:        10 r/s   ← el trabajo arrastra 300× por debajo del techo
```

Encolar y responder al instante devuelve el camino de la petición a sus 0,32 ms. El trabajo se
hace detrás, al ritmo del pool.

> **Subir el techo** y **dejar de caerse del techo** son dos problemas distintos. El peldaño 2
> sirve para verlos separados.

Y eso separa dos números que hoy están pegados: el ritmo al que se **acepta** trabajo y el
ritmo al que se **completa**. Cuando dejen de ser el mismo, aparece la pregunta del peldaño 4:
¿qué pasa cuando aceptas más rápido de lo que completas? La cola crece. Una cola que crece sin
límite es el siguiente fallo.

---

## L. Hallazgo colateral: `GET /jobs` sin paginación

Primer intento de esta medición, contra `/jobs` (la colección) en lugar de `/jobs/0`, con un
servidor que llevaba horas acumulando (~200.000 jobs):

```
p50 ~600 ms, casi igual bajo wait que bajo calculate
```

Casi igual porque el coste no venía de la contención sino del **tamaño del almacén**. Cada GET
hacía: la comprensión de copia sobre 200.000 jobs **con el lock cogido**, `json.dumps` de
200.000 objetos, y varios MB por el socket.

Dos fallos distintos, los dos reales:

**1. Endpoint de colección sin paginación.** O(número de jobs almacenados). Funciona perfecto
en los tests con 5 elementos y tarda 600 ms en producción. Toda API real pagina las
colecciones; ahora hay un número propio que lo justifica.

**2. Lo hace con el lock cogido.** No solo es lento el GET: **bloquea todos los POST durante
600 ms**. Un solo cliente pidiendo la lista tumba el servidor. Es el aviso de los 163 µs de la
copia a dos niveles — despreciable con 3.000 jobs, denegación de servicio autoinfligida con
200.000.

Y una lección de método: con el GET apuntando a la colección, **el medidor también generaba
carga**, y de la peor clase. Se estaba midiendo la interferencia del propio instrumento.
