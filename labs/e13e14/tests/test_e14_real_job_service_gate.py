"""Offline checks for the intentionally narrow service outage scope."""
import copy
import unittest

from test_e14_runtime import ROOT, load_module

gate = load_module(ROOT / 'labs/e13e14/real_job_service_gate.py', 'e14_service_gate_test')


class ServiceScope(unittest.TestCase):
    def setUp(self):
        self.before = {r: {'container_id': str(i), 'started_at': 'before'}
                       for i, r in enumerate(gate.PORTS)}

    def test_only_echecker_may_be_stopped(self):
        after = {r: dict(v, running=r != gate.ROLE) for r, v in self.before.items()}
        gate.verify_only_stopped(self.before, after)
        wrong = copy.deepcopy(after)
        wrong['draft']['running'] = False
        with self.assertRaises(gate.GateError):
            gate.verify_only_stopped(self.before, wrong)

    def test_expected_restart_not_replacement_or_other_restart(self):
        after = copy.deepcopy(self.before)
        after[gate.ROLE]['started_at'] = 'after'
        gate.verify_only_restarted(self.before, after)
        for role, field, value in [(gate.ROLE, 'container_id', 'replacement'),
                                    ('draft', 'started_at', 'after'),
                                    (gate.ROLE, 'started_at', 'before')]:
            wrong = copy.deepcopy(after)
            wrong[role][field] = value
            with self.subTest(role=role, field=field), self.assertRaises(gate.GateError):
                gate.verify_only_restarted(self.before, wrong)


if __name__ == '__main__':
    unittest.main()
