"""Error types for the protocol package."""


class ProtocolError(Exception):
    """A protocol file is missing, unparseable, invalid, or misused.

    The message is human-readable and names the offending field where one
    can be identified.
    """
