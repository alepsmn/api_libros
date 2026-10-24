import time

def waiting(ms):
    time.sleep(ms/1000)

def calculating(ms):
    # time.perf_counter()/process_time()/thread_time()
    end = time.thread_time() + ms/1000
    while time.thread_time() < end:
        pass

# t = time.perf_counter()
# waiting(100)
# print(time.perf_counter()-t)

# t = time.perf_counter()
# calculating(100)
# print(time.perf_counter()-t)