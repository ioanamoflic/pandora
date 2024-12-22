from typing import Any

import numpy as np
import time
import cirq
import qualtran as qt
import requests
import json
import pandas as pd
# from rigetti_resource_estimation import gs_equivalence as gseq
# from rigetti_resource_estimation.estimation_pipeline import estimation_pipeline
# from rigetti_resource_estimation import widgetization
# from rigetti_resource_estimation import transpile
# from rigetti_resource_estimation import translators

# pyLIQTR 1.3.3
from pyLIQTR.ProblemInstances.getInstance import getInstance
from pyLIQTR.clam.lattice_definitions import SquareLattice, TriangularLattice
from pyLIQTR.BlockEncodings.getEncoding import getEncoding, VALID_ENCODINGS
from pyLIQTR.qubitization.qsvt_dynamics import qsvt_dynamics, simulation_phases
from pyLIQTR.qubitization.qubitized_gates import QubitizedWalkOperator
from pyLIQTR.circuits.operators.AddMod import AddMod as pyLAM

# https://github.com/isi-usc-edu/qb-gsee-benchmark, commit 4c547e8
from qb_gsee_benchmark.qre import get_df_qpe_circuit
from qb_gsee_benchmark.utils import retrieve_fcidump_from_sftp

# pyscf v2.7.0
from pyscf import ao2mo, tools

# openfermion v1.6.1
from openfermion import InteractionOperator


def make_qsvt_circuit(model, encoding, times=1.0, p_algo=0.95):
    """Make a QSVT based circuit from pyLIQTR"""
    eps = (1 - p_algo) / 2
    scaled_times = times * model.alpha
    phases = simulation_phases(times=scaled_times, eps=eps, precompute=False, phase_algorithm="random")
    gate_qsvt = qsvt_dynamics(encoding=encoding, instance=model, phase_sets=phases)
    return gate_qsvt.circuit


def make_fh_circuit(N=2, times=1.0, p_algo=0.95):
    """Helper function to build Fermi-Hubbard circuit."""
    # Create Fermi-Hubbard Instance
    J = -1.0
    U = 2.0
    model = getInstance("FermiHubbard", shape=(N, N), J=J, U=U, cell=SquareLattice)
    return make_qsvt_circuit(model, encoding=getEncoding(VALID_ENCODINGS.PauliLCU), times=times, p_algo=p_algo)


def make_transverse_ising_circuit(N=3):
    model = getInstance("Heisenberg", shape=(N, N), J=(0, 0, 1.0), h=(0.1, 0, 0), cell=TriangularLattice)
    return make_qsvt_circuit(model, encoding=getEncoding(VALID_ENCODINGS.PauliLCU))


def make_mg_coating_walk_op(EC=13, data_path="."):
    """Adapted from Notebook sent on May 27th from Nam H Nguyen (Boeing).

    Requirements: Unzip the 'mgcoating_data.zip' archive alongside this notebook.

    Original source code and data provided by HRL and Boeing as part of the DARPA Quantum
    Benchmarking program. Reproduced with permission.
    """
    data_dir = f"{data_path}/mgcoating_data/"
    hamhdf5 = f"{data_dir}mg_dimer_{EC}_ham.hdf5"
    gridhdf5 = f"{data_dir}mg_dimer_{EC}_grid.hdf5"
    slab = getInstance('ElectronicStructure', filenameH=hamhdf5, filenameG=gridhdf5)
    N_DPW = slab._N  # number of real space grid points
    alpha = slab.alpha

    encoding = getEncoding(VALID_ENCODINGS.LinearT, instance=slab, energy_error=1e-3, control_val=1)
    registers = qt._infra.gate_with_registers.get_named_qubits(encoding.signature)

    ### Circuit for a single Walk operator
    walk_op = QubitizedWalkOperator(encoding)
    walk_circuit = cirq.Circuit(walk_op.on_registers(**registers))
    return walk_circuit


def make_cyclic_o3_circuit(data_path="."):
    """Adapted from notebook sent on November 8th, 2024 from Nam H Nguyen (Boeing).

    Requirements: Ensure the 'c60.fcidump' file is downloaded alongside this notebook.

    Original source code and data provided by HRL and Boeing as part of the DARPA Quantum
    Benchmarking program. Reproduced with permission.
    """

    def integrals2intop(h1, eri, ecore):
        norb = h1.shape[0]
        h2_so = np.zeros((2 * norb, 2 * norb, 2 * norb, 2 * norb))
        h1_so = np.zeros((2 * norb, 2 * norb))
        # Populate h1_so
        h1_so[:norb, :norb] = h1
        h1_so[norb:, norb:] = h1_so[:norb, :norb]

        # Populate h2_so
        h2_so[0::2, 0::2, 0::2, 0::2] = eri
        h2_so[1::2, 1::2, 0::2, 0::2] = eri
        h2_so[0::2, 0::2, 1::2, 1::2] = eri
        h2_so[1::2, 1::2, 1::2, 1::2] = eri

        # Transpose from 1122 to 1221
        h2_so = np.transpose(h2_so, (1, 2, 3, 0))
        return InteractionOperator(constant=ecore, one_body_tensor=h1_so, two_body_tensor=h2_so)

    filename = f'{data_path}/c60.fcidump'
    fci_data = tools.fcidump.read(filename)
    eri = ao2mo.restore('s1', fci_data['H2'], fci_data['NORB'])
    hamiltonian_op = integrals2intop(h1=fci_data['H1'], eri=eri, ecore=fci_data['ECORE'])
    mol_instance = getInstance('ChemicalHamiltonian', mol_ham=hamiltonian_op)

    br = 7
    df_error_threshold = 1e-3
    sf_error_threshold = 1e-8
    energy_error = 1e-3

    df_encoding = getEncoding(instance=mol_instance, encoding=VALID_ENCODINGS.DoubleFactorized,
                              df_error_threshold=df_error_threshold, sf_error_threshold=sf_error_threshold, br=br,
                              energy_error=energy_error)

    walk_op = QubitizedWalkOperator(df_encoding)

    registers = qt._infra.gate_with_registers.get_named_qubits(walk_op.signature)
    walk_circuit = cirq.Circuit(walk_op.on_registers(**registers))
    return walk_circuit


def make_hc_circuit(data_path="."):
    """Adapted from L3Harris contributions to open source repository maintained by USC/ISI.

    Requirements: Obtain 'darpa-qb-key.ppk' from Basecamp and place alongside this notebook. See:
    https://3.basecamp.com/3613864/buckets/26823103/messages/7222735635

    Requirements: Ensure the JSON data file is downloaded alongside this notebook.

    Problem instance specification (JSON data) reproduced from:
    https://github.com/isi-usc-edu/qb-gsee-benchmark/tree/main/problem_instances

    Data file retrieval from SFTP uses code adapted from:
    https://github.com/isi-usc-edu/qb-gsee-benchmark/blob/main/examples/get_problem_lqre.py
    """
    ppk_path = f'{data_path}/darpa-qb-key.ppk'
    username = "darpa-qb"

    with open(f'{data_path}/problem_instance.mn_mono.cb40f3f7-ffe8-40e8-4544-f26aad5a8bd8.json', 'r') as f:
        problem_instance = json.load(f)
    solution_data: list[dict[str, Any]] = []
    results = {}
    data_url = problem_instance['instance_data'][0]["supporting_files"][0]["instance_data_object_url"]
    fci = retrieve_fcidump_from_sftp(data_url, username=username, ppk_path=ppk_path)
    circuit, num_shots, hardware_failure_tolerance_per_shot = get_df_qpe_circuit(fci=fci,
                                                                                 error_tolerance=1.6e-3,
                                                                                 failure_tolerance=1e-2,
                                                                                 square_overlap=0.8 ** 2,
                                                                                 df_threshold=1e-3
                                                                                 )
    return circuit.circuit
