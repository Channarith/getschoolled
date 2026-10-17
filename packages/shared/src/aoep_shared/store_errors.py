"""Errors for Redis-backed system-of-record stores."""


class DurableStoreError(RuntimeError):
    """Redis could not serve the system of record.

    Callers must fail the request. Falling back to a per-process memory
    copy splits rooms and sessions across replicas.
    """
