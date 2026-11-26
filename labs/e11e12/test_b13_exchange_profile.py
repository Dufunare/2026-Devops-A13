import hashlib
import unittest

from exchange_profile import load_exchange_profile


class B13ExchangeProfileTests(unittest.TestCase):
    def test_b13_e12_binding_preserves_draft_runtime(self):
        profile_sha = "f0367b454aff9cb0a5304e3e3330b61d4bbd01c3f19069eaf5930a1664d3733b"

        # 与 ECS 暂存请求中的运行配置一致。
        runtime = {
            "units": [["main.o", "main.c"], ["helper.o", "helper.c"]],
            "config_file": "config.h",
            "config_after": "#define VALUE 2\n",
            "config_mode": "overwrite",
            "header_check": "output",
            "exec_image": "draft",
            "require_make_flags": True,
            "expected_output": "1",
            "expected_output_after": "2",
            "build_target": "app",
            "clean_target": "clean",
            "flags_allowed": ["-O0"],
            "recursive_scan": False,
            "strict_sources": True,
        }
        request = {
            "mode": "e12",
            "base": "cb6545b3e8eddda5bec89b12ee390ae5e930f822",
            "target": "5cfaf2014db78635b61d88b62760481834a344d5",
            "exchange_profile_id": "b13-level-v1",
            "profile_sha256": profile_sha,
            "expected_output": "1",
            "profile": runtime,
        }

        raw, actual_runtime, shared = load_exchange_profile(request)

        self.assertEqual(hashlib.sha256(raw).hexdigest(), profile_sha)
        self.assertEqual(shared["id"], "b13-level-v1")
        self.assertEqual(actual_runtime, runtime)
