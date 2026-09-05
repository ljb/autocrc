import os
import tempfile
from unittest import TestCase

# CRC-sums of the payloads used throughout the tests
PAYLOAD = b"hello\n"
PAYLOAD_CRC = "363A3020"
OTHER_PAYLOAD = b"other content"
OTHER_PAYLOAD_CRC = "98E82DF9"
EMPTY_CRC = "00000000"


class TempDirTestCase(TestCase):
    """Base class for tests that need a throwaway directory tree to CRC-check."""

    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._cleanup, temp_dir)
        self.temp_dir = temp_dir.name

    @staticmethod
    def _cleanup(temp_dir):
        # Read-only files created by write_file() would otherwise block the removal
        for root, _, files in os.walk(temp_dir.name):
            for file_name in files:
                os.chmod(os.path.join(root, file_name), 0o644)
        temp_dir.cleanup()

    def path(self, *parts):
        return os.path.join(self.temp_dir, *parts)

    def write_file(self, name, content=PAYLOAD, mode=None):
        """Creates a file relative to the temp dir, creating parent directories as needed."""
        path = self.path(name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as file_:
            file_.write(content)
        if mode is not None:
            os.chmod(path, mode)
        return path

    def write_sfv(self, name, lines):
        return self.write_file(name, "".join(f"{line}\n" for line in lines).encode())
