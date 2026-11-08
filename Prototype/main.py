import streamlit as st
import io               # For capturing output
from dotenv import load_dotenv
import os
from otari import OtariClient
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

    OTARI_API_KEY = os.getenv("OTARI_API_KEY")
    OTARI_MODEL = os.getenv("OTARI_MODEL")
    OTARI_VERIFICATION_MODEL = os.getenv("OTARI_VERIFICATION_MODEL")
    EXTRACTION_POLICY = "claims-selector"
    VERIFICATION_POLICY = "assert-claiming"

    base_client = OtariClient(api_base=OTARI_URL,
                        api_key=OTARI_API_KEY)

    st.set_page_config(
        page_title="Otari Fact Checker AI agent",
        page_icon="📓"
    )

    st.title("Otari Fact Checker AI agent")

    st.text_input("Enter your name:", key="user_name")
    name = st.session_state.get("user_name", "").strip()
    if not name:
        st.info("Enter your name to start. Each name gets a $0.20 usage budget, " \
        "I trust you don't abuse in this demo.")
        st.stop()

    user_id = "name:" + name.lower()

    client = base_client

    with st.expander("Models used"):
        st.write("Extraction and search routing:", OTARI_MODEL)
        st.write("Fact verification:", OTARI_VERIFICATION_MODEL)

    st.header("1. Fact-check with claim extraction and web search")
    st.caption(
        "Splits your text into individual claims, decides which need a web "
        "search, then verifies each claim separately."
    )
    user_statement = st.text_area(
        "Statement to fact-check (claim extraction + web search):",
        key="fact_check_statement",
    )
    if user_statement:
        display_fact_checking(client, EXTRACTION_POLICY, VERIFICATION_POLICY, user_statement)

    st.divider()

    st.header("2. Check with Wikipedia MCP")
    st.caption(
        "Verifies the whole statement using only Wikipedia MCP server. " \
        "No claim extraction and no web search."
    )
    wiki_statement = st.text_area(
        "Statement to check against Wikipedia (MCP):",
        key="wiki_statement",
    )
    if wiki_statement:
        display_wiki_search(client, VERIFICATION_POLICY, wiki_statement)


def display_fact_checking(client, extraction_policy, verification_policy, user_statement):
    st.write("You entered:", user_statement)

    with st.spinner("Extracting claims and deciding whether search is needed..."):
        try:
            claims, resp = try3(
                extract_and_classify_claims, client, extraction_policy, user_statement
            )
        except ValueError:
            st.error("Claim extraction failed after three attempts. Please try again.")
            return

    display_model(resp)    
    display_reasoning(resp)

    with st.expander("Extracted claims:"):
        for item in claims["claims"]:
            st.info(f"Claim: {item['claim']}\n Is established: {item['is_established']}")

    if not claims["claims"]:
        st.info("No verifiable factual claims found.")

    for item in claims["claims"]:
        claim = item["claim"]
        is_established = item["is_established"]

        st.markdown(f"**Claim:** **{claim}**")
        st.write("Needs web search:", not is_established, "Explanation:", item["explanation"])

        with st.spinner("Asserting claimed fact..."):
            try:
                answer, resp = try3(
                    assert_fact, client, verification_policy, claim, not is_established
                )
            except ValueError:
                st.error("Fact verification failed after three attempts. Please try again.")
                return

        display_model(resp)
        display_reasoning(resp)
        display_otari_tool_activity(resp)

        st.markdown(f"**Fact-checking result:** {answer['verdict']}")
        st.markdown(f"**Explanation:** {answer['explanation']}")

        st.write("Citations provided by the model:")
        if answer["citations"]:
            for citation in answer["citations"]:
                st.write(citation)
        else:
            st.info("No citations provided.")

    st.success("Analysis complete.")


def display_wiki_search(client, verification_policy, wiki_statement):
    st.write("You entered:", wiki_statement)

    with st.spinner("Checking the statement with the Wikipedia MCP server..."):
        try:
            answer, resp = assert_via_wikipedia(client, verification_policy, wiki_statement)
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

    display_model(resp)
    display_reasoning(resp)

    with st.expander(f"Wikipedia MCP tool usage ({len(answer['mcp_activity'])}/{MAX_MCP_CALLS} calls)"):
        if answer["mcp_activity"]:
            st.json(answer["mcp_activity"])
        else:
            st.info("The model did not call any Wikipedia MCP tool.")

    st.markdown(f"**Fact-checking result:** {answer['verdict']}")
    st.markdown(f"**Explanation:** {answer['explanation']}")

    st.success("Wikipedia check complete.")


def display_otari_tool_activity(resp):
    with st.expander("Otari tool activity"):
        tool_calls = resp.additional_properties.get("otari_tool_calls")
        if tool_calls is None:
            st.info(
                        "No tool activity metadata returned. "
                    )
        elif not tool_calls:
            st.info("Otari reported no tool calls.")
        else:
            st.caption(
                        "Inspect the results and any errors below. "
                    )
            st.json(tool_calls)

def display_reasoning(resp):
    with st.expander("Reasoning"):
        st.info(fetch_reasoning(resp))

def display_model(resp):
    with st.expander("Model used"):
        st.write(resp.model)

if __name__ == "__main__":
    main()
