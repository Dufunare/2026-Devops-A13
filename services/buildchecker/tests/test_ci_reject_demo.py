"""Regression for the successful version command.

PR #8 first used an intentionally wrong expected exit code of 1 to demonstrate
protected-main rejection. After recording that rejection, restore the correct
expected value of 0; the command implementation is unchanged.
"""
from buildchecker.cli import main


def test_version_command_success_exit_code():
    assert main(["version"]) == 0
