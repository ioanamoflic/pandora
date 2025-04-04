import pyLIQTR.qubitization.qsvt


class LazyProxy:
    def __init__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs
        self._instance = None

    def _instantiate(self):
        if self._instance is None:
            print(f"Lazily instantiating QSVT_real_polynomial...")
            self._instance = pyLIQTR.qubitization.qsvt.QSVT_real_polynomial(*self._args, **self._kwargs)

    def __getattr__(self, name):
        self._instantiate()
        return getattr(self._instance, name)
