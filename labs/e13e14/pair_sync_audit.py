"""Offline peer-side synchronous five-stage original verification (Linux/WSL).

No HTTP replay, Docker execution, source modification or claim of SSH identity.
The caller must obtain expected source/request/candidate hashes and the original
/course job URI and host bind path independently from the agreed release record.
"""
import argparse
import json
import re
from pathlib import Path

from real_job_gate import verify_result
from e14_gate import require


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--job',type=Path,required=True)
    p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--request-sha256',required=True)
    p.add_argument('--candidate-sha256',required=True)
    p.add_argument('--original-job-uri',required=True)
    p.add_argument('--course-source',required=True)
    p.add_argument('--source-record',type=Path,required=True)
    p.add_argument('--expected-source',required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    require(re.fullmatch(r'[0-9a-f]{40}',a.expected_source)
            and a.source_record.read_text().strip()==a.expected_source,
            'PEER_DECLARED_SOURCE_MISMATCH')
    require(a.out.resolve() != a.job.resolve() and
            not a.out.resolve().is_relative_to(a.job.resolve()), 'PEER_RECEIPT_INSIDE_ORIGINALS')
    summary=verify_result(a.job,a.request_sha256,a.candidate_sha256,
                          candidate_path=a.candidate,original_job_uri=a.original_job_uri,
                          course_source=a.course_source)
    summary.update(declared_source_commit=a.expected_source,
                   source_record_verified=True, live_execution=False,
                   formal_pair_acceptance=False, operator_identity_verified=False,
                   scope='offline verification of peer-supplied synchronous originals')
    with a.out.open('x',encoding='utf-8') as stream:
        json.dump(summary,stream,ensure_ascii=False,indent=2)
        stream.write('\n')
    print('PAIR_SYNC_ORIGINALS_GATE=PASS')
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':
    main()
