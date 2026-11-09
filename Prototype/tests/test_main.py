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
