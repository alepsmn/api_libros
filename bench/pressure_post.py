import json, threading, time, urllib.request
import numpy as np
import matplotlib.pyplot as plt

def post(url_base, i, results, failures):
    url = f"{url_base}/jobs"
    body = json.dumps({"payload": {"type": "calculate", "ms": 100}}).encode('utf-8')
    headers = {"Content-Type": "application/json"}

    counter = 0
    end_time = time.perf_counter() + 20
    while time.perf_counter() < end_time:
        counter += 1
        t0 = time.perf_counter()
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method='POST')
            with urllib.request.urlopen(req) as answer:
                status = answer.status
                answer.read()
                results.append(time.perf_counter() - t0)
        except Exception as e:
            failures.append(f"Failure, thread {i} - try {counter}: error - {e}")

def concurrent_posts():
    url = "http://localhost:8000"
    N = 16
    #N = [128, 256, 512, 1024]

    
    # Listas para almacenar las métricas de la gráfica
    n_values = []
    p50_values = []
    p99_values = []

    
    zread_list = []
    results = []
    failures = []

    t_ini = time.perf_counter()

    for i in range(N):
        zread = threading.Thread(
            target=post, args=(url, i, results, failures)
        )
        zread_list.append(zread)
        zread.start()

    for zread in zread_list:
        zread.join()

    t_end = time.perf_counter()

    for failure in failures:
        print(failure)

    total_time = t_end - t_ini
    throughput = len(results) / total_time if total_time > 0 else 0
    errors = len(failures)

    # --- p50, p99 ---
    if results:
        # x1000  s -> ms
        p50 = np.percentile(results, 50) * 1000 # results[len(results)//2]
        p99 = np.percentile(results, 99) * 1000
    else:
        p50, p99 = 0, 0

    print(
        f"For N: {N:2d} -> Throughput = {throughput:7.2f} req/s | "
        f"p50 = {p50:6.1f}ms | p99 = {p99:6.1f}ms | Errors = {errors}"
    )

    if results:
        n_values.append(N)
        p50_values.append(p50)
        p99_values.append(p99)

    # --- GENERACIÓN DE LA GRÁFICA ---
    dibujar_grafica(n_values, p50_values, p99_values)


def dibujar_grafica(n, p50, p99):
    plt.figure(figsize=(10, 6))
    
    # Dibujar líneas de percentiles
    plt.plot(n, p50, marker='o', linestyle='-', color='b', label='p50 (Mediana)')
    plt.plot(n, p99, marker='s', linestyle='--', color='r', label='p99 (Peor caso)')
    
    # Configuración de ejes y etiquetas
    plt.title('Impacto de la Concurrencia en la Latencia del Servidor')
    plt.xlabel('Número de Hilos Concurrentes (N)')
    plt.ylabel('Latencia (milisegundos)')
    plt.xscale('log', base=2)  # Escala logarítmica base 2 ya que doblas los hilos (1, 2, 4, 8...)
    plt.xticks(n, labels=[str(x) for x in n])
    plt.grid(True, which="both", linestyle=":", alpha=0.6)
    plt.legend()
    
    # Guardar y mostrar
    plt.savefig('latencias_benchmark.png', dpi=300)
    print("\n[INFO] Gráfica guardada exitosamente como 'latencias_benchmark.png'")
    plt.show()


if __name__ == "__main__":
    concurrent_posts()