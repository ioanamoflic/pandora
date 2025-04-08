import pyLIQTR

from pyLIQTR.qubitization.qubitized_gates import QubitizedRotation


class LazyProxy:
    def __init__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs
        self._instance = None
        # TODO assign this somehow based on the process id
        self._should_decompose = False

    def _instantiate(self):
        if self._instance is None:
            print(f"Lazily instantiating QubitizedRotation...")
            self._instance = QubitizedRotation(*self._args, **self._kwargs)

    def on_registers(self, *args, **kwargs):
        print("Attempting to call on_registers...")
        if not self._should_decompose:
            return []
        self._instantiate()
        print(f"Lazy call to on_registers...")
        return self._instance.on_registers(*args, **kwargs)

    def __getattr__(self, name):
        self._instantiate()
        return getattr(self._instance, name)


# monkey-patch
print("Monkey-patching")
pyLIQTR.qubitization.qubitized_gates.QubitizedRotation = lambda *args, **kwargs: LazyProxy(*args, **kwargs)
