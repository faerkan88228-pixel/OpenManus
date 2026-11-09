import hashlib
import unittest

from pydantic import ValidationError

from app.config import DaytonaSettings
from app.prometheus_runtime import (
    RunRequest,
    RuntimeSkillContext,
    render_skill_context,
)


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
            source_url="https://github.com/example/repo/blob/main/components/FactionDashboard.tsx",
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


if __name__ == "__main__":
    unittest.main()
