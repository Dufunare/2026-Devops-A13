#!/usr/bin/env bash
set -euo pipefail
trap 'run_code=$?; printf "%s\n" "$run_code" > /root/241830088/integrated-e7-course.exit' EXIT
cd /root/241830088/e7-integration
git rev-parse HEAD > work/course-provenance/source-sha.txt
git status --short > work/course-provenance/source-status.txt
cp /root/241830088/run-integrated-e7.sh work/course-provenance/host-run.sh
python3 scripts/doctor.py --out work/course-provenance/env.json > work/course-provenance/doctor.log
python3 -m unittest discover -s tests/e7 -v > work/course-provenance/oracle-tests.log 2>&1
python3 scripts/verify_pair13_delivery.py > work/course-provenance/pair13-delivery-check.json
python3 scripts/lab_cloud.py build --image course1020-buildchecker:241830088-integrated --out work/build-course-01 --build-timeout 1200
printf '0\n' > work/course-provenance/build.exit
docker run --rm --network none course1020-buildchecker:241830088-integrated cat /opt/toolchain.lock > work/course-provenance/toolchain.lock
python3 scripts/lab_cloud.py gate --image course1020-buildchecker:241830088-integrated --out work/e7-course-01
printf '0\n' > work/course-provenance/gate.exit
python3 scripts/verify_e7_a_evidence.py --gate-dir work/e7-course-01/gate > work/course-provenance/evidence-audit.json
python3 scripts/secret_scan.py . --history --image course1020-buildchecker:241830088-integrated > work/course-provenance/secret-scan.txt
printf '0\n' > work/course-provenance/scan.exit
cat work/course-provenance/evidence-audit.json
