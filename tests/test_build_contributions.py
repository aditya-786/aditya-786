import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import build_contributions as contributions


def pull_request(number, state, repo="keephq/keep", decision=None):
    return {
        "number": number,
        "title": f"fix: contribution {number}",
        "url": f"https://github.com/{repo}/pull/{number}",
        "state": state,
        "reviewDecision": decision,
        "repository": {"nameWithOwner": repo, "stargazerCount": 1200},
    }


def page(nodes, next_cursor=None):
    return {
        "data": {
            "user": {
                "pullRequests": {
                    "nodes": nodes,
                    "pageInfo": {
                        "hasNextPage": next_cursor is not None,
                        "endCursor": next_cursor,
                    },
                }
            }
        }
    }


class ContributionsTests(unittest.TestCase):
    @patch.object(contributions, "gh_json")
    def test_fetches_all_pages_without_repository_searches(self, gh_json):
        first = pull_request(1, "MERGED")
        second = pull_request(2, "OPEN")
        gh_json.side_effect = [page([first], "next-page"), page([second])]

        self.assertEqual(contributions.prs(), [first, second])

        first_args = gh_json.call_args_list[0].args[0]
        second_args = gh_json.call_args_list[1].args[0]
        self.assertEqual(first_args[:2], ["api", "graphql"])
        self.assertIn("author=aditya-786", first_args)
        self.assertNotIn("endCursor=next-page", first_args)
        self.assertIn("endCursor=next-page", second_args)

    @patch.object(contributions, "prs")
    def test_renders_live_states_and_filters_to_curated_projects(self, prs):
        prs.return_value = [
            pull_request(1, "MERGED"),
            pull_request(2, "OPEN", decision="APPROVED"),
            pull_request(3, "CLOSED"),
            pull_request(4, "OPEN", repo="other/project"),
        ]
        readme = "before\n<!-- CONTRIB:START -->\nstale\n<!-- CONTRIB:END -->\nafter"

        result = contributions.build_contributions(readme)

        self.assertIn("1 merged · 1 approved · 1 in review", result)
        self.assertIn("1 open-source projects", result)
        self.assertIn("1.2k★", result)
        self.assertIn("https://github.com/keephq/keep/pull/1", result)
        self.assertIn("approved-1f6feb", result)
        self.assertNotIn("/pull/3", result)
        self.assertNotIn("other/project", result)
        self.assertTrue(result.startswith("before\n"))
        self.assertTrue(result.endswith("\nafter"))

    @patch.object(contributions, "time")
    @patch.object(contributions.subprocess, "run")
    def test_retries_rate_limit_then_returns_result(self, run, clock):
        run.side_effect = [
            subprocess.CalledProcessError(1, ["gh"], stderr="HTTP 429: abuse detection"),
            subprocess.CompletedProcess(["gh"], 0, stdout=json.dumps({"data": "ok"})),
        ]

        self.assertEqual(contributions.gh_json(["api", "graphql"]), {"data": "ok"})

        self.assertEqual(run.call_count, 2)
        clock.sleep.assert_called_once_with(60)

    @patch.object(contributions, "time")
    @patch.object(contributions.subprocess, "run")
    def test_retries_are_bounded_and_preserve_github_error(self, run, clock):
        run.side_effect = subprocess.CalledProcessError(
            1, ["gh"], stderr="HTTP 429: secondary rate limit"
        )

        with self.assertRaisesRegex(RuntimeError, "HTTP 429: secondary rate limit"):
            contributions.gh_json(["api", "graphql"])

        self.assertEqual(run.call_count, 3)
        self.assertEqual([call.args[0] for call in clock.sleep.call_args_list], [60, 120])

    @patch.object(contributions, "time")
    @patch.object(contributions.subprocess, "run")
    def test_does_not_retry_permission_errors(self, run, clock):
        run.side_effect = subprocess.CalledProcessError(
            1, ["gh"], stderr="HTTP 403: Resource not accessible by integration"
        )

        with self.assertRaisesRegex(RuntimeError, "Resource not accessible"):
            contributions.gh_json(["api", "graphql"])

        run.assert_called_once()
        clock.sleep.assert_not_called()

    @patch.object(contributions, "prs", side_effect=RuntimeError("GitHub unavailable"))
    def test_api_failure_leaves_readme_unchanged(self, prs):
        with tempfile.TemporaryDirectory() as directory:
            readme = Path(directory) / "README.md"
            readme.write_text("existing profile")
            with patch.object(contributions, "README", readme):
                with self.assertRaisesRegex(RuntimeError, "GitHub unavailable"):
                    contributions.main()
            self.assertEqual(readme.read_text(), "existing profile")


if __name__ == "__main__":
    unittest.main()
