!!! tip
    You might have seen loop constructions around [`threading.Event`][] like this:

    ```python
    while not stop_event.is_set():
        do_work()
    ```

    You can get the same behavior by writing a `do_work()` that always returns `True`.
    *bgt* checks for shutdown between calls, so your work unit does not need to manage a stop event.

    Waiting for a wakeup is a strictly optional (but very useful) feature.
