import unittest

from streamlit.testing.v1 import AppTest


def app_with_mock_checks():
    import streamlit as st
    from unittest.mock import patch
    import main

    with (
        patch.object(main, "OtariClient"),
        patch.object(
            main, "display_fact_checking",
            side_effect=lambda *args: st.write("Search submitted: " + args[-1]),
        ),
        patch.object(
            main, "display_wiki_search",
            side_effect=lambda *args: st.write("Wiki submitted: " + args[-1]),
        ),
    ):
        main.main()


def app_with_mock_results(mode, verdict="supported", with_activity=True, with_citations=True):
    from types import SimpleNamespace
    from unittest.mock import patch
    import main

    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(reasoning="Internal model details"))],
        additional_properties={
            "otari_tool_calls": [{"name": "web_search"}] if with_activity else []
        },
    )
    answer = {
        "verdict": verdict,
        "explanation": "A user-facing explanation.",
        "citations": ["https://example.org/evidence"] if with_citations else [],
        "mcp_activity": [{"name": "search_wikipedia"}] if with_activity else [],
    }
    claims = {
        "claims": [
            {"claim": "First claim", "is_established": False, "explanation": "Needs search."},
            {"claim": "Second claim", "is_established": True, "explanation": "Established."},
        ]
    }
    with (
        patch.object(main, "extract_and_classify_claims", new=lambda *args: (claims, response)),
        patch.object(main, "assert_fact", new=lambda *args: (answer, response)),
        patch.object(main, "assert_via_wikipedia", return_value=(answer, response)),
    ):
        if mode == "search":
            main.display_fact_checking(None, "name:test", "extract", "verify", "Some claims")
        else:
            main.display_wiki_search(None, "name:test", "verify", "Some claims")


class ResultPresentationTests(unittest.TestCase):
    def run_results(self, mode, **kwargs):
        app = AppTest.from_function(
            app_with_mock_results, args=(mode,), kwargs=kwargs, default_timeout=15
        ).run()
        self.assertFalse(app.exception)
        return app

    def assert_result_layout(self, app, count):
        children = list(app.main.children.values())
        cards = [child for child in children if child.type == "flex_container"]
        self.assertEqual(len(cards), count)
        for card in cards:
            self.assertTrue(card.proto.flex_container.border)
            self.assertEqual(card.subheader[0].value, "Fact-checking result")
            self.assertFalse(any(
                item.value.startswith("**Confidence:**") for item in card.markdown
            ))
            self.assertIn("**Explanation:** A user-facing explanation.",
                          [item.value for item in card.markdown])
            previous = children[children.index(card) - 1]
            self.assertEqual(previous.type, "expander")
            self.assertEqual(previous.label, "Reasoning and tool activity")
            self.assertEqual(previous.text[0].value, "Internal model details")
        for expander in app.expander:
            self.assertFalse(expander.proto.expanded)
            self.assertEqual(len(expander.subheader), 0)
        return cards

    def test_search_keeps_each_result_outside_collapsed_details(self):
        app = self.run_results("search")
        cards = self.assert_result_layout(app, 2)
        self.assertEqual(app.expander[0].label, "Claim extraction details")
        for card in cards:
            self.assertIn("https://example.org/evidence",
                          [item.value for item in card.markdown])
        self.assertEqual([len(expander.json) for expander in app.expander], [0, 1, 1])
        self.assertEqual(app.success[0].value, "Analysis complete.")

    def test_wiki_shows_sources_and_keeps_mcp_details_secondary(self):
        app = self.run_results("wiki")
        cards = self.assert_result_layout(app, 1)
        self.assertIn("https://example.org/evidence",
                      [item.value for item in cards[0].markdown])
        self.assertEqual(len(app.expander[0].json), 1)
        self.assertEqual(app.success[0].value, "Wikipedia check complete.")

    def test_all_verdicts_stay_visible_without_sources_or_tool_calls(self):
        for mode in ("search", "wiki"):
            for verdict in ("supported", "refuted", "controversial", "insufficient_evidence"):
                with self.subTest(mode=mode, verdict=verdict):
                    app = self.run_results(
                        mode, verdict=verdict, with_activity=False, with_citations=False
                    )
                    cards = self.assert_result_layout(app, 2 if mode == "search" else 1)
                    for card in cards:
                        self.assertIn(
                            f"**Verdict:** {verdict.replace('_', ' ').capitalize()}",
                            [item.value for item in card.markdown],
                        )
                        self.assertIn("No citations provided.",
                                      [item.value for item in card.caption])
                    self.assertFalse(app.json)


class SubmissionTests(unittest.TestCase):
    def setUp(self):
        self.app = AppTest.from_function(
            app_with_mock_checks, default_timeout=15
        ).run()
        self.app.text_input(key="user_name").input("Test user").run()
        self.assertFalse(self.app.exception)

    def assert_submissions(self, expected):
        self.assertFalse(self.app.exception)
        self.assertEqual(
            [item.value for tab in self.app.tabs for item in tab.markdown],
            expected,
        )

    def test_only_submitted_form_runs_with_both_statements_filled(self):
        self.assertEqual(
            [tab.label for tab in self.app.tabs], ["Search", "Wiki", "Math"]
        )
        self.app.text_area(key="wiki_statement").input("Wiki claim")
        self.app.button[1].click().run()
        self.assert_submissions(["Wiki submitted: Wiki claim"])

        self.app.text_area(key="fact_check_statement").input("Search claim")
        self.app.button[0].click().run()
        self.assert_submissions(["Search submitted: Search claim"])

        self.app.button[1].click().run()
        self.assert_submissions(["Wiki submitted: Wiki claim"])
        self.assertEqual(
            self.app.text_area(key="fact_check_statement").value, "Search claim"
        )
        self.assertEqual(self.app.text_area(key="wiki_statement").value, "Wiki claim")

        self.app.run()
        self.assert_submissions([])

    def test_empty_submissions_do_not_run_checks(self):
        for button in self.app.button:
            button.click().run()
            self.assert_submissions([])


if __name__ == "__main__":
    unittest.main()
