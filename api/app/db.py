from google.cloud import firestore


def get_db() -> firestore.AsyncClient:
    # TODO(F1): share one client per process; use the emulator when FIRESTORE_EMULATOR_HOST is set.
    return firestore.AsyncClient()
