class LazyProxy:
    proc_id = None

    def __init__(self, pyliqtr_class, proc_id, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs
        self._instance = None
        self.proc_id = proc_id
        self._pyliqtr_class = pyliqtr_class
        print(f"LazyProxy instantiating ... ")

    def set_proc_id(self, proc_id):
        self.proc_id = proc_id

    def _instantiate(self):
        if self._instance is None:
            print(f"Lazily instantiating {self._pyliqtr_class}...")
            self._instance = self._pyliqtr_class(*self._args, **self._kwargs)

    def on_registers(self, *args, **kwargs):
        print("Attempting to call on_registers...")
        if self.proc_id is None:
            return []
        self._instantiate()
        print(f"Lazy call to on_registers from proc {self.proc_id}...")
        return self._instance.on_registers(*args, **kwargs)

    def __getattr__(self, name):
        self._instantiate()
        return getattr(self._instance, name)
