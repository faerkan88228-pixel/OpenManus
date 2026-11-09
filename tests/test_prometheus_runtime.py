import unittest

from pydantic import ValidationError

from app.prometheus_runtime import (
    RuntimeSkillContext,
    RunRequest,
    render_skill_context,
)


class TestPrometheusRuntimeContext(unittest.TestCase):
    def test_context_is_source_attributed_and_delimited(self):
        context = RuntimeSkillContext(
            name="Responsive UI",
            source_url="https://github.com/example/repo/blob/main/skills/ui/SKILL.md",
            source_sha="a" * 40,
            content="Use a mobile-first layout.",
        )
        rendered = render_skill_context([context])
        self.assertIn("Responsive UI", rendered)
        self.assertIn(context.source_url, rendered)
        self.assertIn(context.source_sha, rendered)
        self.assertIn("UNTRUSTED SKILL CONTENT", rendered)
        self.assertIn("Use a mobile-first layout.", rendered)

    def test_rejects_non_github_source(self):
        with self.assertRaises(ValidationError):
            RuntimeSkillContext(
                name="Untrusted",
                source_url="https://example.com/skill.md",
                source_sha="b" * 40,
                content="Do something",
            )

    def test_rejects_invalid_git_blob_sha(self):
        with self.assertRaises(ValidationError):
            RuntimeSkillContext(
                name="Invalid SHA",
                source_url="https://github.com/example/repo/blob/main/SKILL.md",
                source_sha="not-a-sha",
                content="Instructions",
            )

    def test_request_limits_skill_context_count(self):
        contexts = [
            RuntimeSkillContext(
                name=f"Skill {index}",
                source_url=f"https://github.com/example/repo/blob/main/skills/{index}/SKILL.md",
                source_sha=f"{index:040x}",
                content="x",
            )
            for index in range(9)
        ]
        with self.assertRaises(ValidationError):
            RunRequest(goal="Build an app", skill_contexts=contexts)

    def test_empty_context_renders_empty_string(self):
        self.assertEqual(render_skill_context([]), "")


if __name__ == "__main__":
    unittest.main()
