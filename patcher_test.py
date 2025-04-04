from monkey_patching.lazy_load import *

# monkey-patch
cirq.ops.gate_operation.GateOperation = lambda *args, **kwargs: LazyProxy(*args, **kwargs)

# this should not call the constructor of GateOperation
print("Declaring obj, not yet instantiating")
gate_op = cirq.ops.gate_operation.GateOperation(gate=cirq.CNOT,
                                                qubits=[cirq.NamedQubit("a"), cirq.NamedQubit("b")])

# the constructor is called now
print("Accessing member of GateOperation")
print(gate_op.gate)
print(gate_op.qubits)
