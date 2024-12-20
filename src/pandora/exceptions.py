"""
    Exception Objects
"""


class PandoraException(Exception):
    """
        General widget exception object
    """

    def __init__(self, msg=None, **kwargs):
        # Let the doc strings be the default error message
        if msg is None:
            msg = self.__doc__
        super().__init__(msg, **kwargs)


class WrongPandoraObjectArgument(PandoraException):
    """
        Wrong arguments passed for Pandora object.
    """


class CirqGateHasNoPandoraEquivalent(PandoraException):
    """
        Cirq name class object has no equivalent in the Pandora gate representation.
    """


class PandoraGateOrderingError(PandoraException):
    """
        The gate id requested does not exist.
    """


class PandoraWrappedGateMissingLinks(PandoraException):
    """
        Pandora wrapped gate has missing links for the neighbours.
    """


class BadPandoraInput(PandoraException):
    """
        Can only insert PandoraGate objects into the database.
    """


class TupleNotFound(PandoraException):
    """
        Element not found in the database.
    """


class PandoraGateWrappedMissingQubits(PandoraException):
    """
        Qubit is none.
    """
