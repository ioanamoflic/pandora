import math

from pandora import Pandora
from pandora.connection_util import db_multi_threaded, stop_all_lurking_procedures, reset_database_id
from pandora.gate_translator import PandoraGateTranslator


class PandoraOptimizer(Pandora):
    """
    The optimizer of Pandora. This class is used to control the types of rewrite rules that run in parallel in Pandora.

    There are two types of stored procedures used for the optimisation, used depending on the context:
        I. when the stored circuit is smaller (for ex. <= 1e6 gates):
            * we care about a more precise sampling method, where we trade sampling accuracy for speed
            * it is advised to use utilize_bernoulli = True. This is a row-level sampling method used in
              the stored procedures. The optimisations are performed, if applicable, on the sampled rows.
            * bernoulli_proba (0-100) is the percentage of rows (out of the total row count) on which the optimisations
              are applied at a time.

        II. when the stored circuit is larger (for ex. > 1e6 gates):
            * we trade speed for the sampling accuracy
            * it is advised to use utilize_bernoulli = False. This performs block-level sampling and returns a
             set of (maximum) block_size rows
            * the sample is not completely random but works well enough for large tables

        For parallel optimisation:
            * It is most useful to use multiple optimisations running in parallel. The number of parallel processes is
            controlled by nproc. The method dedicated_nproc can overwrite the class nproc if the user prefers a more
            fine-grained control over a specific optimisation type.

        For running a fixed number of optimisations:
            * set run_nr to control the number of times a certain rewrite rule will be applied.
              This is most likely used for testing purposes.
            * e.g. for run_nr = 1000, the optimisation will run until it applies its rewrite rule exactly 1000 times. If
              the optimisation is not applicable, the optimisation will run infinitely (or until timeout).

        For running optimisations in a simulated annealing-like way:
            *  run_nr defaults to math.inf, therefore the optimisations run infinitely or until timeout (given in sec)
               time has passed
    """

    LARGE_RUN_NR = int(1e6)
    RESET_ID = int(1e6)

    def __init__(self,
                 bernoulli_percentage: float = False,
                 utilize_bernoulli: bool = None,
                 nproc: int = 1,
                 timeout: int = 100,
                 block_size: int = None,
                 run_nr: int = LARGE_RUN_NR,
                 ):
        super().__init__()
        self.run_nr = run_nr
        self.block_size = block_size
        self.nproc = nproc
        self.utilize_bernoulli = utilize_bernoulli
        self.bernoulli_percentage = bernoulli_percentage
        self.timeout = timeout

        self._thread_proc = list()

    def _call_thread_proc(self, thread_proc) -> None:
        """
        Append a specific configuration to the global process list
        """
        self._thread_proc.append(thread_proc)

    def _add_stopper(self):
        """
        Add stopper such that stored procedures don't run forever.
        """
        stopper = f"call stopper({self.timeout})"
        self._call_thread_proc((1, stopper))

    def _reset_table_id(self):
        """
        Used to avoid unique key violation for procedures which insert gates.
        """
        reset_database_id(self.connection,
                          table_name='linked_circuit',
                          large_buffer_value=self.RESET_ID)

    def start(self) -> None:
        """
        Start the optimisation algorithm according to the created configuration.
        """
        self._add_stopper()
        self._reset_table_id()
        db_multi_threaded(thread_proc=self._thread_proc)

    def clear(self):
        """
        Clear all current stored procedures.
        """
        self._thread_proc.clear()

    def stop(self):
        """
        Stop all procedures currently running in Pandora.
        """
        stop_all_lurking_procedures(self.connection)

    def cancel_single_qubit_gates(self,
                                  gate_types: tuple[PandoraGateTranslator, PandoraGateTranslator],
                                  gate_params: tuple[float, float] = (1.0, 1.0),
                                  dedicated_nproc: int = None) -> None:
        """
        Cancels pairs of single-qubit gates

        ---- L(param_left) ---- R(param_right) ----  =  ------------

        from the linked_list Pandora table.

        """

        type_left, type_right = gate_types
        param_left, param_right = gate_params

        if not self.utilize_bernoulli:
            stored_procedure = f"call cancel_single_qubit({type_left}, {type_right}, {param_left}, {param_right}," \
                               f"{self.block_size},{self.run_nr})"
        else:
            stored_procedure = f"call cancel_single_qubit_bernoulli({type_left}, {type_right}, {param_left}, " \
                               f"{param_right},{self.bernoulli_percentage}, {self.run_nr})"""

        self._call_thread_proc((self.nproc if not dedicated_nproc else dedicated_nproc, stored_procedure))

    def cancel_two_qubit_gates(self,
                               gate_types: tuple[PandoraGateTranslator, PandoraGateTranslator],
                               gate_params: tuple[float, float] = (1.0, 1.0),
                               dedicated_nproc: int = None) -> None:
        """
        Cancels pairs of two-qubit gates

        ---- L(param_left) ---- R(param_right) ----    ------------
             |                  |                   =
        ---- L(param_left) ---- R(param_right) ----    ------------

        on the linked_list Pandora table.

        """
        type_left, type_right = gate_types
        param_left, param_right = gate_params
        if not self.utilize_bernoulli:
            stored_procedure = f"call cancel_two_qubit({type_left}, {type_right}, {param_left}, {param_right},\
                                {self.block_size},{self.run_nr})"
        else:
            stored_procedure = f"call cancel_two_qubit_bernoulli({type_left}, {type_right},{param_left},{param_right}," \
                               f"{self.bernoulli_percentage},{self.run_nr})"
        self._call_thread_proc((self.nproc if not dedicated_nproc else dedicated_nproc, stored_procedure))

    def hhcxhh_to_cx(self,
                     dedicated_nproc: int = None) -> None:

        """
        Applies rewrite rule

             ───H───X───H───      ────@────
                    │                 │
             ───H───@───H───      ────X────

        where applicable on the linked_list Pandora table.
        """

        if not self.utilize_bernoulli:
            stored_procedure = f"call linked_hhcxhh_to_cx({self.block_size},{self.run_nr})"
        else:
            stored_procedure = f"call linked_hhcxhh_to_cx_bernoulli({self.bernoulli_percentage},{self.run_nr})"

        self._call_thread_proc((self.nproc if not dedicated_nproc else dedicated_nproc, stored_procedure))

    def cx_to_hhcxhh(self,
                     dedicated_nproc: int = None) -> None:

        """
        Applies rewrite rule

             ────@────      ───H───X───H───
                 │                 │
             ────X────      ───H───@───H───

        where applicable on the linked_list Pandora table.
        """

        if not self.utilize_bernoulli:
            stored_procedure = f"call linked_cx_to_hhcxhh({self.block_size},{self.run_nr})"
        else:
            stored_procedure = f"call linked_cx_to_hhcxhh_bernoulli({self.bernoulli_percentage},{self.run_nr})"

        self._call_thread_proc((self.nproc if not dedicated_nproc else dedicated_nproc, stored_procedure))

    def fuse_single_qubit_gates(self,
                                gate_types: tuple[PandoraGateTranslator, PandoraGateTranslator, PandoraGateTranslator],
                                gate_params: tuple[float, float, float] = (1.0, 1.0, 1.0),
                                dedicated_nproc: int = None
                                ) -> None:
        """
        Fuses pairs of single-qubit gates

        ────L(param_left)────R(param_right)────  =  ────Res(param_result)─────

        from the linked_list Pandora table.
        """

        type_left, type_right, type_result = gate_types
        param_left, param_right, param_result = gate_params
        if not self.utilize_bernoulli:
            stored_procedure = f"call fuse_single_qubit({type_left},{type_right},{type_result},{param_left}," \
                               f"{param_right},{param_result},{self.block_size},{self.run_nr})"
        else:
            stored_procedure = f"call fuse_single_qubit_bernoulli({type_left},{type_right},{type_result}," \
                               f"{param_left},{param_right},{param_result},{self.bernoulli_percentage},{self.run_nr})"

        self._call_thread_proc((self.nproc if not dedicated_nproc else dedicated_nproc, stored_procedure))

    def commute_rotation_with_control_left(self,
                                           gate_type: PandoraGateTranslator,
                                           gate_param: float = 1.0,
                                           dedicated_nproc: int = None) -> None:

        """
        Applies rewrite rule

             ────@───R─         ──R───@────
                 │                    │
             ────X─────         ──────X────

        where applicable on the linked_list Pandora table.
        """

        if not self.utilize_bernoulli:
            stored_procedure = f"call commute_single_control_right({gate_type},{gate_param}," \
                               f"{self.block_size}, {self.run_nr})"
        else:
            stored_procedure = f"call commute_single_control_right_bernoulli({gate_type},{gate_param}," \
                               f"{self.bernoulli_percentage}, {self.run_nr})"

        self._call_thread_proc((self.nproc if not dedicated_nproc else dedicated_nproc, stored_procedure))

    def commute_rotation_with_control_right(self,
                                            gate_type: PandoraGateTranslator,
                                            gate_param: float = 1.0,
                                            dedicated_nproc: int = None) -> None:

        """
        Applies rewrite rule

             ─R───@─────         ──────@───R─
                  │                    │
             ─────X─────         ──────X─────

        where applicable on the linked_list Pandora table.
        """

        if not self.utilize_bernoulli:
            stored_procedure = f"call commute_single_control_left({gate_type},{gate_param}," \
                               f"{self.block_size},{self.run_nr})"
        else:
            stored_procedure = f"call commute_single_control_left_bernoulli({gate_type}, {gate_param}, " \
                               f"{self.bernoulli_percentage},{self.run_nr})"

        self._call_thread_proc((self.nproc if not dedicated_nproc else dedicated_nproc, stored_procedure))

    def commute_cnots(self,
                      dedicated_nproc: int = None) -> None:

        """
        Applies rewrite rule

        ───────@───         ───@───────@───
               │               │       │
        ───@───X───     =   ───X───@───┼───
           │                       │   │
        ───X───────         ───────X───X───

        where applicable on the linked_list Pandora table.

        """
        if not self.utilize_bernoulli:
            stored_procedure = f"call commute_cx_ctrl_target({self.block_size},{self.run_nr})"
        else:
            stored_procedure = f"call commute_cx_ctrl_target_bernoulli({self.bernoulli_percentage},{self.run_nr})"

        self._call_thread_proc((self.nproc if not dedicated_nproc else dedicated_nproc, stored_procedure))

