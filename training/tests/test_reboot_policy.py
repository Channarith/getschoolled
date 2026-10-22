from reboot_policy import ingest_workers, voice_train_allowed


def test_ingest_stays_at_one_worker_while_the_exam_is_alive():
    assert ingest_workers(80000, True) == 1
    assert ingest_workers(20000, False) == 1
    assert ingest_workers(80000, False) == 2


def test_khmer_does_not_start_while_the_hold_file_is_present():
    assert voice_train_allowed(True) is False
    assert voice_train_allowed(False) is True
