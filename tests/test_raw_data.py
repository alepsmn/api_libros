# unitary test

from api_libros.raw_data import RawData

def test_inmutability_get():
    storage = RawData()
    job = storage.save({"payload": "test_load"}) # esta capa no anade state, result 
    original = storage.get(job['id'])
    original["payload"] = "MUTATED"
    job2 = storage.get(job['id'])

    assert job2["payload"] == "test_load"

def test_inmutability_get_all():
    storage = RawData()

    expected = {} # lo esperado se crea a partir de lo recibido
    for i in range(5):
        job = storage.save({"payload": f"test_load{i}"})
        expected[job["id"]] = f"test_load{i}"

    jobs = storage.get_all()
    for k in list(jobs):
        jobs[k]["payload"] = f"muted_load{k}"

    jobs2 = storage.get_all()
    for k in list(jobs2):
        assert jobs2[k]["payload"] == expected[k]

def test_inmutability_save():
    storage = RawData()
    body = {"payload": "test_load"}
    job = storage.save(body)
    body["payload"] = "MUTATED"

    job2 = storage.get(job['id'])
    assert job2['payload'] == "test_load" 