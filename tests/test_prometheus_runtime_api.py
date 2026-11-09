import os
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.prometheus_runtime import app


class FakeManus:
    def __init__(self):
        self.system_prompt = "OpenManus base policy"
        self.max_steps = 20
        self._initialized = False
        self.run = AsyncMock(return_value="OpenManus completed the task.")


class TestPrometheusRuntimeAPI(unittest.TestCase):
    def setUp(self):
        self.previous_token = os.environ.get("PROMETHEUS_RUNTIME_TOKEN")
        os.environ["PROMETHEUS_RUNTIME_TOKEN"] = "test-runtime-token"
        self.client = TestClient(app)

    def tearDown(self):
        if self.previous_token is None:
            os.environ.pop("PROMETHEUS_RUNTIME_TOKEN", None)
        else:
            os.environ["PROMETHEUS_RUNTIME_TOKEN"] = self.previous_token

    def test_health_identifies_real_runtime(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["runtime"], "openmanus")

    def test_run_requires_runtime_token(self):
        response = self.client.post(
            "/v1/agent/run",
            json={"goal": "Summarize the repository"},
        )
        self.assertEqual(response.status_code, 401)

    def test_run_calls_openmanus_and_loads_reviewed_skill_context(self):
        fake_agent = FakeManus()
        skill = {
            "name": "Repository Analyst",
            "source_url": "https://github.com/example/repo/blob/main/skills/repo/SKILL.md",
            "source_sha": "a" * 40,
            "content": "Inspect the repository structure before proposing changes.",
        }
        with patch(
            "app.prometheus_runtime.Manus.create",
            new=AsyncMock(return_value=fake_agent),
        ):
            response = self.client.post(
                "/v1/agent/run",
                headers={"X-Prometheus-Runtime-Token": "test-runtime-token"},
                json={
                    "goal": "Review repository architecture",
                    "skill_contexts": [skill],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["runtime"], "openmanus")
        self.assertEqual(response.json()["skills_loaded"], 1)
        self.assertIn("Repository Analyst", fake_agent.system_prompt)
        self.assertIn("UNTRUSTED REPOSITORY CONTENT", fake_agent.system_prompt)
        fake_agent.run.assert_awaited_once_with("Review repository architecture")

    def test_run_rejects_non_github_skill_sources(self):
        skill = {
            "name": "External Skill",
            "source_url": "https://example.com/SKILL.md",
            "source_sha": "b" * 40,
            "content": "Do something.",
        }
        response = self.client.post(
            "/v1/agent/run",
            headers={"X-Prometheus-Runtime-Token": "test-runtime-token"},
            json={"goal": "Use this skill", "skill_contexts": [skill]},
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
