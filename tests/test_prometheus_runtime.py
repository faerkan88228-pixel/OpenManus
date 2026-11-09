import hashlib
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.config import DaytonaSettings
from app.prometheus_runtime import (
    RunRequest,
    RuntimeSkillContext,
    configure_agent_tools,
    render_skill_context,
)
from app.tool import ToolCollection


def git_blob_sha1(content: str) -> str:
    raw = content.encode("utf-8")
    return hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest()


class TestPrometheusRuntimeContext(unittest.TestCase):
    def test_context_is_source_attributed_and_delimited(self):
        content = "Use a mobile-first layout."
        context = RuntimeSkillContext(
            name="Responsive UI",
            source_url="https://github.com/example/repo/blob/main/skills/ui/SKILL.md",
            source_sha=git_blob_sha1(content),
            content=content,
        )
        rendered = render_skill_context([context])
        self.assertIn("Responsive UI", rendered)
        self.assertIn(context.source_url, rendered)
        self.assertIn(context.source_sha, rendered)
        self.assertIn("UNTRUSTED REPOSITORY CONTENT", rendered)
        self.assertIn(content, rendered)

    def test_rejects_github_url_with_embedded_credentials(self):
        content = "Do something"
        with self.assertRaises(ValidationError):
            RuntimeSkillContext(
                name="Credential URL",
                source_url="https://user:secret@github.com/example/repo/blob/main/SKILL.md",
                source_sha=git_blob_sha1(content),
                content=content,
            )

    def test_rejects_non_github_source(self):
        content = "Do something"
        with self.assertRaises(ValidationError):
            RuntimeSkillContext(
                name="Untrusted",
                source_url="https://example.com/skill.md",
                source_sha=git_blob_sha1(content),
                content=content,
            )

    def test_rejects_invalid_git_blob_sha(self):
        with self.assertRaises(ValidationError):
            RuntimeSkillContext(
                name="Invalid SHA",
                source_url="https://github.com/example/repo/blob/main/SKILL.md",
                source_sha="not-a-sha",
                content="Instructions",
            )

    def test_rejects_content_that_does_not_match_git_blob_sha(self):
        with self.assertRaises(ValidationError):
            RuntimeSkillContext(
                name="Changed source",
                source_url="https://github.com/example/repo/blob/main/SKILL.md",
                source_sha=git_blob_sha1("reviewed source"),
                content="different source",
            )

    def test_request_limits_skill_context_count(self):
        contexts = [
            RuntimeSkillContext(
                name=f"Skill {index}",
                source_url=(
                    f"https://github.com/example/repo/blob/main/skills/{index}/SKILL.md"
                ),
                source_sha=git_blob_sha1("x"),
                content="x",
            )
            for index in range(9)
        ]
        with self.assertRaises(ValidationError):
            RunRequest(goal="Build an app", skill_contexts=contexts)

    def test_ui_module_context_is_distinguished_from_skill_context(self):
        content = "export function FactionDashboard() { return null; }"
        context = RuntimeSkillContext(
            kind="ui",
            name="Faction Dashboard",
            source_url=(
                "https://github.com/example/repo/blob/main/components/FactionDashboard.tsx"
            ),
            source_sha=git_blob_sha1(content),
            content=content,
        )
        rendered = render_skill_context([context])
        self.assertIn("UI MODULE 1: Faction Dashboard", rendered)
        self.assertIn("UNTRUSTED REPOSITORY CONTENT", rendered)

    def test_empty_context_renders_empty_string(self):
        self.assertEqual(render_skill_context([]), "")

    def test_daytona_credentials_are_optional_without_daytona(self):
        self.assertEqual(DaytonaSettings().daytona_api_key, "")


    def test_unsandboxed_python_tool_is_disabled_by_default(self):

        class FakeTool:
            def __init__(self, name):
                self.name = name

        class FakeAgent:
            available_tools = ToolCollection(
                FakeTool("python_execute"),
                FakeTool("str_replace_editor"),
                FakeTool("terminate"),
            )

        agent = FakeAgent()
        with patch.dict("os.environ", {"OPENMANUS_ENABLE_PYTHON_EXECUTION": "0"}):
            enabled = configure_agent_tools(agent)
        self.assertFalse(enabled)
        self.assertNotIn("python_execute", agent.available_tools.tool_map)
        self.assertIn("str_replace_editor", agent.available_tools.tool_map)

    def test_python_tool_requires_explicit_runtime_opt_in(self):

        class FakeTool:
            def __init__(self, name):
                self.name = name

        class FakeAgent:
            available_tools = ToolCollection(
                FakeTool("python_execute"),
                FakeTool("terminate"),
            )

        agent = FakeAgent()
        with patch.dict("os.environ", {"OPENMANUS_ENABLE_PYTHON_EXECUTION": "1"}):
            enabled = configure_agent_tools(agent)
        self.assertTrue(enabled)
        self.assertIn("python_execute", agent.available_tools.tool_map)


if __name__ == "__main__":
    unittest.main()
