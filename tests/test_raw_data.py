# unitary test
import pytest

from dataclasses import FrozenInstanceError
from api_libros.raw_data import RawData

def test_inmutability_get():
    storage = RawData()
    job = storage.save("calculate",100)
    # Dataclass Frozen -> inmutable
    with pytest.raises(FrozenInstanceError) as exc:
        job.work_type = 'wait'

    # assert "cannot assign to field 'work_type'" in str(exc.value)
    assert exc.type == FrozenInstanceError

def test_storage_map_copy():
    storage = RawData()
    job1 = storage.save("calculate",100) # 0
    job2 = storage.save("calculate",100) # 1
    jobs = storage.get_all()
    job = jobs.pop(0)
    assert storage.get(job.id) is not None