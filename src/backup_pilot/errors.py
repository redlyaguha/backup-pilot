"""Errors shared by CLI and services; codes 5 and 6 are reserved for later modules."""


class BackupPilotError(Exception):
    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code
