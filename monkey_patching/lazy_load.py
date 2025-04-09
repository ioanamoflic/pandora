from pyLIQTR.qubitization.qubitized_gates import QubitizedRotation


class LazyProxy:
    def __init__(self, proc_id, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs
        self._instance = None
        self._proc_id = proc_id
        # print("LazyProxy instantiating...")

    def _instantiate(self):
        if self._instance is None:
            # print(f"Lazily instantiating QubitizedRotation...")
            self._instance = QubitizedRotation(*self._args, **self._kwargs)

    def on_registers(self, *args, **kwargs):
        # print("Attempting to call on_registers...")
        if self._proc_id is None:
            return []
        self._instantiate()
        # print(f"Lazy call to on_registers from proc {self._proc_id}...")
        return self._instance.on_registers(*args, **kwargs)

    def __getattr__(self, name):
        self._instantiate()
        return getattr(self._instance, name)

