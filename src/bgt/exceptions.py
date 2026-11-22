class SuppressedCrashError(RuntimeError):
    """
    A work factory's context manager swallowed the exception that ended a
    loop run.

    Without this exception, the loop run would return without a stop. The
    supervisor would restart it, but the logs could not tell you why the run
    ended.
    """
