from pyLIQTR.qubitization.qsvt import QSVT_real_polynomial


class LazyProxy:
    def __init__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs
        self._instance = None

    def _instantiate(self):
        if self._instance is None:
            print(f"Lazily instantiating QSVT_real_polynomial...")
            self._instance = QSVT_real_polynomial(*self._args, **self._kwargs)

    def __getattr__(self, name):
        self._instantiate()
        return getattr(self._instance, name)


# monkey-patch
print("Monkey-patching")
lazy_QSVT_real_polynomial = lambda *args, **kwargs: LazyProxy(*args, **kwargs)

