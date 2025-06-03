import math

from pandora import Pandora
from pandora.connection_util import db_multi_threaded
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
            * set run_nr to control the number of times a certain rewrite rule will bve applied.
              This is most likely used for testing purposes.
            * e.g. for run_nr = 1000, the optimisation will run until it applies its rewrite rule exactly 1000 times. If
              the optimisation is not applicable, the optimisation will run infinitely (or until timeout).

        For running optimisations in a simulated annealing-like way:
            *  run_nr defaults to math.inf, therefore the optimisations run infinitely until timeout (given in sec) time
            has passed

    """

    def __init__(self,
                 block_size: int,
                 bernoulli_proba: float,
                 utilize_bernoulli: bool,
                 nproc: int = 1,
                 timeout: int = 100,
                 run_nr: int = math.inf,
                 ):
        super().__init__()
        self.run_nr = run_nr
        self.block_size = block_size
        self.nproc = nproc
        self.utilize_bernoulli = utilize_bernoulli
        self.bernoulli_proba = bernoulli_proba
        self.timeout = timeout

    def cancel_single_qubit_gates(self,
                                  gate_type_left: PandoraGateTranslator,
                                  gate_type_right: PandoraGateTranslator,
                                  param_left: float,
                                  param_right: float,
                                  dedicated_nproc: int = None):
        """
        Cancels pairs of single-qubit gates

        ---- L(param_left) ---- R(param_right) ----  =  ------------

        from the linked_list Pandora table.

        """
        if not self.utilize_bernoulli:
            stored_procedure = f"""
                                    call cancel_single_qubit(
                                    {gate_type_left}, 
                                    {gate_type_right}, 
                                    {param_left},
                                    {param_right},
                                    {self.block_size},
                                    {self.run_nr}
                                    )
                                    """
        else:
            stored_procedure = f"""
                                    call cancel_single_qubit_bernoulli(
                                    {gate_type_left}, 
                                    {gate_type_right}, 
                                    {param_left},
                                    {param_right},
                                    {self.bernoulli_proba},
                                    {self.run_nr}
                                    )
                                    """

        stopper = f"call stopper({self.timeout})"
        if not dedicated_nproc:
            db_multi_threaded(thread_proc=[(self.nproc, stored_procedure),
                                           (1, stopper)])
        else:
            db_multi_threaded(thread_proc=[(dedicated_nproc, stored_procedure),
                                           (1, stopper)])

    def cancel_two_qubit_gates(self,
                               gate_type_left: PandoraGateTranslator,
                               gate_type_right: PandoraGateTranslator,
                               param_left: float,
                               param_right: float,
                               dedicated_nproc: int = None):
        """
        Cancels pairs of two-qubit gates

        ---- L(param_left) ---- R(param_right) ----    ------------
             |                  |                   =
        ---- L(param_left) ---- R(param_right) ----    ------------

        from the linked_list Pandora table.

        """
        if not self.utilize_bernoulli:
            stored_procedure = f"""
                                    call cancel_two_qubit(
                                    {gate_type_left}, 
                                    {gate_type_right}, 
                                    {param_left},
                                    {param_right},
                                    {self.block_size},
                                    {self.run_nr}
                                    )
                                    """
        else:
            stored_procedure = f"""
                                    call cancel_two_two_bernoulli(
                                    {gate_type_left}, 
                                    {gate_type_right}, 
                                    {param_left},
                                    {param_right},
                                    {self.bernoulli_proba},
                                    {self.run_nr}
                                    )
                                    """

        stopper = f"call stopper({self.timeout})"
        if not dedicated_nproc:
            db_multi_threaded(thread_proc=[(self.nproc, stored_procedure),
                                           (1, stopper)])
        else:
            db_multi_threaded(thread_proc=[(dedicated_nproc, stored_procedure),
                                           (1, stopper)])
        # TODO add rest

