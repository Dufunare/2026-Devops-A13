import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"scripts"))
from validate_e2_v2 import validate_report
def read(r):return json.loads((ROOT/r).read_text(encoding="utf-8"))
class Pair13V2Tests(unittest.TestCase):
    def test_valid(self):self.assertEqual([],validate_report(read("contracts/examples/v2/md-report.valid.json")))
    def test_unresolved_path(self):self.assertTrue(validate_report(read("contracts/examples/v2/invalid/unresolved-with-path.json")))
    def test_unsafe_path(self):self.assertTrue(validate_report(read("contracts/examples/v2/invalid/unsafe-dependency.json")))
    def test_empty_evidence(self):self.assertTrue(validate_report(read("contracts/examples/v2/invalid/empty-evidence.json")))
    def test_unknown_core(self):self.assertTrue(validate_report(read("contracts/examples/v2/invalid/unknown-core-field.json")))
    def test_tool_job(self):self.assertTrue(validate_report(read("contracts/examples/v2/invalid/tool-without-producer-job.json")))
    def test_optional_commit_matches(self):
        d=copy.deepcopy(read("contracts/examples/v2/md-report.valid.json"));d["findings"][0]["commit"]="b"*40
        self.assertTrue(any("repository.commit" in x for x in validate_report(d)))
if __name__=="__main__":unittest.main()
