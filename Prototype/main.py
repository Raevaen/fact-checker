import streamlit as st
import io               # For capturing output
from dotenv import load_dotenv
import os
from otari import OtariClient
from mainfunctions import extract_and_classify_claims, assert_fact, try3, fetch_reasoning

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

    client = OtariClient(api_base=OTARI_URL,
                        api_key=OTARI_API_KEY)

    st.set_page_config(
        page_title="Otari Fact Checker AI agent",
        page_icon="🔎"
    )

    st.title("Otari Fact Checker AI agent")
    
    with st.expander("Models used"):
        st.write("Extraction and search routing:", OTARI_MODEL)
        st.write("Fact verification:", OTARI_VERIFICATION_MODEL)

    user_statement = st.text_area("Enter a statement to fact-check:")
    if user_statement:
        st.write("You entered:", user_statement)

        with st.spinner("Extracting claims and deciding whether search is needed..."):
            try:
                claims, resp = try3(
                    extract_and_classify_claims, client, EXTRACTION_POLICY, user_statement
                )
            except ValueError:
                st.error("Claim extraction failed after three attempts. Please try again.")
                st.stop()

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
                        assert_fact, client, VERIFICATION_POLICY, claim, not is_established
                    )
                except ValueError:
                    st.error("Fact verification failed after three attempts. Please try again.")
                    st.stop()

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


if __name__ == "__main__":
    main()
