import streamlit as st
import io               # For capturing output
from dotenv import load_dotenv
import os
from otari import OtariClient
from otari.errors import AuthenticationError, InsufficientFundsError
from otari._client.exceptions import ApiException
from mainfunctions import (
    extract_and_classify_claims, assert_fact, try3, fetch_reasoning,
    assert_via_wikipedia, MAX_MCP_CALLS,
)

def main() -> None:
    load_dotenv()
    OTARI_URL = os.getenv(
        "OTARI_BASE_URL",
        "http://localhost:8000"
    )

    # Must be an Otari *service key* (dashboard: API keys -> Create key ->
    # Advanced -> Service key, with a default end-user budget). A regular key
    # rejects requests whose `user` field names anyone but the key's own user:
    # "'user' field does not match the authenticated API key's user".
    OTARI_API_KEY = os.getenv("OTARI_SERVICE_KEY") or os.getenv("OTARI_API_KEY")
    OTARI_MODEL = os.getenv("OTARI_MODEL")
    OTARI_VERIFICATION_MODEL = os.getenv("OTARI_VERIFICATION_MODEL")
    EXTRACTION_POLICY = "claims-selector"
    VERIFICATION_POLICY = "assert-claiming"

    client = OtariClient(api_base=OTARI_URL,
                        api_key=OTARI_API_KEY)

    st.set_page_config(
        page_title="Otari Fact Checker AI agent",
        page_icon="📓"
    )

    st.title("Otari Fact Checker AI agent")

    st.write("Demo of the Fact Checker AI agent for the Otari hackathon started during MozFest 2026." \
             " Each user gets a limited usage budget for the demo and many security measures are missing, so please use responsibly.")

    st.text_input("Enter your name:", key="user_name")
    name = st.session_state.get("user_name", "").strip()
    if not name:
        st.info("Enter your name to start. Each name gets a $0.20 usage budget, " \
        "I trust you don't abuse in this demo.")
        st.stop()

    user_id = "name:" + name.lower()

    # with st.expander("Models used"):
    #     st.write("Extraction and search routing:", OTARI_MODEL)
    #     st.write("Fact verification:", OTARI_VERIFICATION_MODEL)

    search_tab, wiki_tab, math_tab = st.tabs(["Search", "Wiki", "Math"])

    with search_tab:
        st.header("Fact-check with claim extraction and web search")
        st.caption(
            "Splits your text into individual claims, decides which need a web "
            "search, then verifies each claim separately."
        )
        with st.form("search_form"):
            user_statement = st.text_area(
                "Statement to fact-check (claim extraction + web search):",
                key="fact_check_statement",
            )
            search_submitted = st.form_submit_button("Search")

        if search_submitted and user_statement:
            display_fact_checking(
                client, user_id, EXTRACTION_POLICY, VERIFICATION_POLICY, user_statement
            )

    with wiki_tab:
        st.header("Check with Wikipedia MCP")
        st.caption(
            "Verifies the whole statement using only Wikipedia MCP server. "
            "No claim extraction and no web search."
        )
        with st.form("wiki_form"):
            wiki_statement = st.text_area(
                "Statement to check against Wikipedia (MCP):",
                key="wiki_statement",
            )
            wiki_submitted = st.form_submit_button("Check Wikipedia")

        if wiki_submitted and wiki_statement:
            display_wiki_search(client, user_id, VERIFICATION_POLICY, wiki_statement)

    with math_tab:
        pass


def display_fact_checking(client, user_id, extraction_policy, verification_policy, user_statement):
    st.write("You entered:", user_statement)

    with st.spinner("Extracting claims and deciding whether search is needed..."):
        try:
            claims, resp = try3(
                extract_and_classify_claims, client, user_id, extraction_policy, user_statement
            )
        except ValueError:
            st.error("Claim extraction failed after three attempts. Please try again.")
            return
        except (AuthenticationError, InsufficientFundsError) as exc:
            display_gateway_error(exc)
            return

    with st.expander("Claim extraction details", expanded=False):
        display_reasoning(resp)
        st.caption("Extracted claims")
        for item in claims["claims"]:
            st.write(f"Claim: {item['claim']}\n Is established: {item['is_established']}")

    if not claims["claims"]:
        st.info("No verifiable factual claims found.")

    for item in claims["claims"]:
        claim = item["claim"]
        is_established = item["is_established"]

        st.markdown(f"**Claim:** **{claim}**")

        with st.spinner("Asserting claimed fact..."):
            try:
                answer, resp = try3(
                    assert_fact, client, user_id, verification_policy, claim, not is_established
                )
            except ValueError:
                st.error("Fact verification failed after three attempts. Please try again.")
                return
            except (AuthenticationError, InsufficientFundsError) as exc:
                display_gateway_error(exc)
                return

        with st.expander("Reasoning and tool activity", expanded=False):
            st.caption("Search decision")
            st.write("Needs web search:", not is_established)
            st.write(item["explanation"])
            display_reasoning(resp)
            display_otari_tool_activity(resp)

        display_fact_check_result(answer)

    st.success("Analysis complete.")


def display_wiki_search(client, user_id, verification_policy, wiki_statement):
    st.write("You entered:", wiki_statement)

    with st.spinner("Checking the statement with the Wikipedia MCP server..."):
        try:
            answer, resp = assert_via_wikipedia(client, user_id, verification_policy, wiki_statement)
        except (AuthenticationError, InsufficientFundsError) as exc:
            display_gateway_error(exc)
            return
        except ApiException as exc:
            request_id = exc.headers.get("otari-request-id") if exc.headers else None
            st.error(
                f"Wikipedia MCP request failed (status {exc.status}, request {request_id}). "
                "The tool outcome may be unknown, so it was not retried."
            )
            return
        except ValueError as exc:
            st.error(f"Wikipedia check failed: {exc}")
            return

    with st.expander("Reasoning and tool activity", expanded=False):
        display_reasoning(resp)
        st.caption(f"Wikipedia MCP tool usage ({len(answer['mcp_activity'])}/{MAX_MCP_CALLS} calls)")
        if answer["mcp_activity"]:
            st.json(answer["mcp_activity"])
        else:
            st.caption("The model did not call any Wikipedia MCP tool.")

    display_fact_check_result(answer)

    st.success("Wikipedia check complete.")


def display_fact_check_result(answer):
    with st.container(border=True):
        st.subheader("Fact-checking result")
        st.markdown(f"**Verdict:** {answer['verdict'].replace('_', ' ').capitalize()}")
        st.markdown(f"**Explanation:** {answer['explanation']}")
        st.markdown("**Sources cited by the model**")
        if answer["citations"]:
            for citation in answer["citations"]:
                st.write(citation)
        else:
            st.caption("No citations provided.")


def display_gateway_error(exc):
    if isinstance(exc, InsufficientFundsError):
        st.warning(
            "You've used up your $0.20 demo budget. It comes back when the "
            "budget period resets. Thanks for trying the fact checker!"
        )
    else:
        st.error(
            "The gateway rejected this user id. The app must run on an Otari "
            "service key so each name gets its own budget (dashboard: API keys "
            "-> Create key -> Advanced -> Service key). "
            f"Details: {exc}"
        )


def display_otari_tool_activity(resp):
    st.caption("Otari tool activity")
    tool_calls = resp.additional_properties.get("otari_tool_calls")
    if tool_calls is None:
        st.caption("No tool activity metadata returned.")
    elif not tool_calls:
        st.caption("Otari reported no tool calls.")
    else:
        st.json(tool_calls)

def display_reasoning(resp):
    st.caption("Model reasoning")
    st.text(fetch_reasoning(resp))

def display_model(resp):
    with st.expander("Model used"):
        st.write(resp.model)

if __name__ == "__main__":
    main()
