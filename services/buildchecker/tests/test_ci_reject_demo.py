"""Course-required protected-PR rejection demonstration.

This deliberately incorrect oracle is repaired in the same PR after recording
the failed CI run and actual protected-main merge rejection.
"""
from buildchecker.cli import main


def test_version_command_success_exit_code():
    assert main(["version"]) == 1
