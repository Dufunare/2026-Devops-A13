import copy, json, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts"))
from validate_e2 import validate_report, validate_request
def read(r): return json.loads((ROOT/r).read_text(encoding="utf-8"))
class Tests(unittest.TestCase):
    def test_full(self): self.assertEqual([],validate_request(read("contracts/examples/full-check.request.json")))
    def test_incremental(self): self.assertEqual([],validate_request(read("contracts/examples/incremental-check.request.json")))
    def test_no_baseline(self):
        d=read("contracts/examples/incremental-check.request.json"); del d["input"]["baseline"]; self.assertTrue(validate_request(d))
    def test_commit_mismatch(self):
        d=read("contracts/examples/incremental-check.request.json"); d["input"]["baseline"]["commit"]="c"*40; self.assertTrue(validate_request(d))
    def test_config_mismatch(self):
        d=read("contracts/examples/incremental-check.request.json"); d["input"]["environment"]["configuration_id"]="clang-default"; self.assertTrue(validate_request(d))
    def test_report(self): self.assertEqual([],validate_report(read("contracts/artifacts/job-full-a13-001/md-report.json")))
    def test_report_commit_mismatch(self):
        d=copy.deepcopy(read("contracts/artifacts/job-full-a13-001/md-report.json")); d["findings"][0]["commit"]="b"*40; self.assertTrue(validate_report(d))
if __name__=="__main__": unittest.main()
