import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class UiIsolationTests(unittest.TestCase):
    def load_prepare(self):
        path = ROOT / "scripts" / "prepare_ui_local.py"
        self.assertTrue(path.exists(), "independent runtime configuration is missing")
        spec = importlib.util.spec_from_file_location("prepare_ui_local", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_rewrites_connections_and_paths_without_changing_model_key(self):
        module = self.load_prepare()
        original = (
            "DATABASE_URL=postgresql+psycopg://audit:test-password@127.0.0.1:15439/audit\n"
            "REDIS_URL=redis://127.0.0.1:6389/0\n"
            "AI_API_KEY=test-provider-key\n"
            "CODEQL_BIN=D:/semflow-audit/.tools/codeql/codeql.exe\n"
            "ARTIFACT_ROOT=D:/semflow-audit/artifacts\n"
        )
        independent_root = ROOT.parent / "semflow-audit-ui"
        result = module.build_local_config(original, independent_root, 15440, 16380)
        self.assertIn("127.0.0.1:15440/audit", result)
        self.assertIn("REDIS_URL=redis://127.0.0.1:16380/0", result)
        self.assertIn("AI_API_KEY=test-provider-key", result)
        self.assertIn("FRONTEND_HOST=http://127.0.0.1:5174", result)
        self.assertIn("ARTIFACT_ROOT=" + (independent_root / "artifacts").as_posix(), result)
        self.assertNotIn("D:/semflow-audit/", result)

    def test_refuses_original_project_root(self):
        module = self.load_prepare()
        with self.assertRaises(ValueError):
            module.build_local_config("DATABASE_URL=postgresql://a:b@localhost/audit\n", Path("D:/semflow-audit"), 15440, 16380)


if __name__ == "__main__":
    unittest.main()
