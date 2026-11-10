"""Unit tests ensuring every Otari request is bound to the end user.

User binding happens on the chat-completion requests (the `user` field is how a
service key attributes spend to an end user). The MCP routes carry no `user`
parameter in otari 0.4.1, so the tests also guard that the MCP path is called
with the real generated signatures (via autospec) and works end to end.

Run with:  python -m unittest test_user_binding -v
"""

import json
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, create_autospec, patch

from otari._client.api.mcp_api import McpApi
from otari._client.models import CCChatCompletionMessageFunctionToolCall
from otari._client.models.cc_function import CCFunction
from otari._client.models.mcp_execute_request import McpExecuteRequest

import mainfunctions
from mainfunctions import (
    MAX_MCP_CALLS,
    assert_fact,
    assert_via_wikipedia,
    extract_and_classify_claims,
    get_mcp_tools,
)

USER_ID = "name:alice"
MODEL = "openai/gpt-oss-120b"

VERDICT_JSON = json.dumps({
    "verdict": "supported",
    "explanation": "ok",
    "citations": [],
})

CLAIMS_JSON = json.dumps({
    "claims": [
        {"claim": "Paris is the capital of France.",
         "is_established": True,
         "explanation": "Stable general knowledge."}
    ]
})


def completion_response(content=None, tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls, reasoning="r")
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        model=MODEL,
        id="resp-1",
        additional_properties={},
    )


def make_tool_call(call_id="call_1", name="search_wikipedia", arguments='{"query": "France"}'):
    call = CCChatCompletionMessageFunctionToolCall(
        id=call_id,
        function=CCFunction(name=name, arguments=arguments),
        type="function",
    )
    # Responses wrap the concrete call in a union holder exposing actual_instance.
    return SimpleNamespace(actual_instance=call, to_dict=call.to_dict)


def assert_every_completion_bound_to_user(testcase, client):
    testcase.assertGreater(client.completion.call_count, 0)
    for mock_call in client.completion.call_args_list:
        testcase.assertEqual(mock_call.kwargs.get("max_tool_iterations"), 24)
        testcase.assertEqual(
            mock_call.kwargs.get("user"),
            USER_ID,
            f"completion call not bound to user: {mock_call}",
        )


class UserBindingCompletionTests(unittest.TestCase):
    """Every chat completion must carry user=<end user id>."""

    def test_extract_and_classify_claims_binds_user(self):
        client = MagicMock()
        client.completion.return_value = completion_response(content=CLAIMS_JSON)

        result, resp = extract_and_classify_claims(client, USER_ID, MODEL, "some text")

        self.assertEqual(len(result["claims"]), 1)
        assert_every_completion_bound_to_user(self, client)

    def test_assert_fact_with_web_search_binds_user_and_enables_tool(self):
        client = MagicMock()
        client.completion.return_value = completion_response(content=VERDICT_JSON)

        answer, resp = assert_fact(client, USER_ID, MODEL, "a claim", search=True)

        self.assertEqual(answer["verdict"], "supported")
        assert_every_completion_bound_to_user(self, client)
        prompt = client.completion.call_args.kwargs["messages"][0]["content"]
        self.assertNotIn("confidence", prompt.lower())
        tools = client.completion.call_args.kwargs["tools"]
        self.assertEqual(tools, [{"type": "otari_web_search", "max_uses": 4}])

    def test_assert_fact_without_search_binds_user(self):
        client = MagicMock()
        client.completion.return_value = completion_response(content=VERDICT_JSON)

        assert_fact(client, USER_ID, MODEL, "a claim", search=False)

        assert_every_completion_bound_to_user(self, client)
        self.assertEqual(client.completion.call_args.kwargs["tools"], [])


class McpFlowTests(unittest.TestCase):
    """The Wikipedia MCP flow binds the user on every completion and calls the
    MCP API with its real otari 0.4.1 signatures (autospec enforces them)."""

    def setUp(self):
        self.catalog = SimpleNamespace(
            tools=[SimpleNamespace(
                name="search_wikipedia",
                description="Search Wikipedia",
                input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
            )],
            server_id=uuid.uuid4(),
            server_revision="rev-1",
        )
        self.mcp_result = SimpleNamespace(
            is_error=False,
            content=[SimpleNamespace(actual_instance=SimpleNamespace(text="France's capital is Paris."))],
        )
        patcher = patch.object(mainfunctions, "McpApi", create_autospec(McpApi))
        self.mcp_api_cls = patcher.start()
        self.addCleanup(patcher.stop)
        self.mcp_api = self.mcp_api_cls.return_value
        self.mcp_api.mcp_list_mcp_tools.return_value = self.catalog
        self.mcp_api.mcp_execute_mcp_tool.return_value = self.mcp_result

    def test_get_mcp_tools_uses_real_signature(self):
        client = MagicMock()
        catalog, tools = get_mcp_tools(client)

        self.assertIs(catalog, self.catalog)
        self.assertEqual(tools[0]["function"]["name"], "search_wikipedia")
        # Autospec would have raised if McpApi(client._api, user=...) or any
        # other invalid argument were used.
        self.mcp_api_cls.assert_called_once_with(client._api)

    def test_assert_via_wikipedia_binds_user_on_every_completion(self):
        client = MagicMock()
        client.completion.side_effect = [
            completion_response(tool_calls=[make_tool_call()]),
            completion_response(content=VERDICT_JSON),
        ]

        answer, resp = assert_via_wikipedia(client, USER_ID, MODEL, "a statement")

        self.assertEqual(answer["verdict"], "supported")
        self.assertEqual(len(answer["mcp_activity"]), 1)
        self.assertEqual(client.completion.call_count, 2)
        assert_every_completion_bound_to_user(self, client)
        prompt = client.completion.call_args_list[0].kwargs["messages"][0]["content"]
        self.assertNotIn("confidence", prompt.lower())

    def test_mcp_execute_called_once_with_valid_request_and_no_user_kwarg(self):
        client = MagicMock()
        client.completion.side_effect = [
            completion_response(tool_calls=[make_tool_call()]),
            completion_response(content=VERDICT_JSON),
        ]

        assert_via_wikipedia(client, USER_ID, MODEL, "a statement")

        self.mcp_api.mcp_execute_mcp_tool.assert_called_once()
        execute_call = self.mcp_api.mcp_execute_mcp_tool.call_args
        self.assertNotIn("user", execute_call.kwargs)
        request = execute_call.args[0]
        self.assertIsInstance(request, McpExecuteRequest)
        self.assertEqual(request.tool_name, "search_wikipedia")
        self.assertEqual(request.mcp_server_id, self.catalog.server_id)
        self.assertEqual(request.server_revision, self.catalog.server_revision)
        self.assertEqual(request.arguments, {"query": "France"})

    def test_mcp_call_limit_forces_final_answer(self):
        client = MagicMock()
        responses = [
            completion_response(tool_calls=[make_tool_call(call_id=f"call_{i}")])
            for i in range(MAX_MCP_CALLS)
        ]
        responses.append(completion_response(content=VERDICT_JSON))
        client.completion.side_effect = responses

        answer, resp = assert_via_wikipedia(client, USER_ID, MODEL, "a statement")

        self.assertEqual(len(answer["mcp_activity"]), MAX_MCP_CALLS)
        assert_every_completion_bound_to_user(self, client)
        # The final round must offer no tools and forbid tool choice.
        final_kwargs = client.completion.call_args.kwargs
        self.assertEqual(final_kwargs["tools"], [])
        self.assertEqual(final_kwargs["tool_choice"], "none")


class AppWiringTests(unittest.TestCase):
    """main.py must thread user_id down to every mainfunctions call."""

    def setUp(self):
        patcher = patch.object(mainfunctions, "McpApi", create_autospec(McpApi))
        mcp_api_cls = patcher.start()
        self.addCleanup(patcher.stop)
        mcp_api = mcp_api_cls.return_value
        mcp_api.mcp_list_mcp_tools.return_value = SimpleNamespace(
            tools=[], server_id=uuid.uuid4(), server_revision="rev-1",
        )

    def test_display_fact_checking_binds_user(self):
        import main

        client = MagicMock()
        client.completion.side_effect = [
            completion_response(content=CLAIMS_JSON),   # claim extraction
            completion_response(content=VERDICT_JSON),  # claim verification
        ]

        main.display_fact_checking(client, USER_ID, "policy-a", "policy-b", "text")

        assert_every_completion_bound_to_user(self, client)

    def test_display_wiki_search_binds_user(self):
        import main

        client = MagicMock()
        client.completion.return_value = completion_response(content=VERDICT_JSON)

        main.display_wiki_search(client, USER_ID, "policy-b", "statement")

        assert_every_completion_bound_to_user(self, client)


if __name__ == "__main__":
    unittest.main()
