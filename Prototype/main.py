import streamlit as st
import io               # For capturing output
from dotenv import load_dotenv
import os
from otari import OtariClient
from mainfunctions import extract_claims, is_established_fact, assert_fact

load_dotenv()
OTARI_URL = os.getenv(
    "OTARI_BASE_URL",
    "http://localhost:8000"
)

OTARI_API_KEY = os.getenv("OTARI_API_KEY")
OTARI_MODEL = os.getenv("OTARI_MODEL")
OTARI_VERIFICATION_MODEL = os.getenv("OTARI_VERIFICATION_MODEL")


SYSTEM_PROMPT = "You are a concise, friendly truth-seeking journalist."

client = OtariClient(api_base=OTARI_URL, 
                    api_key=OTARI_API_KEY)

st.title("Otari Fact Checker")
with st.expander("Models used"):
    st.write("Extraction and search routing:", OTARI_MODEL)
    st.write("Fact verification:", OTARI_VERIFICATION_MODEL)

user_statement = st.text_area("Enter a statement to fact-check:")
if user_statement:
    st.write("You entered:", user_statement)
    
    with st.spinner("Extracting claims..."):
        claims = extract_claims(client, OTARI_MODEL, user_statement)

    st.write("Extracted claims:", claims)

    for claim in claims["claims"]:
        st.write(f"Claim: {claim}")

        with st.spinner("Checking whether web search is needed..."):
            established = is_established_fact(client, OTARI_MODEL, claim)
            is_established = established["established"]

        st.write("Is an established fact:", is_established)
        st.write("Needs web search:", not is_established)

        with st.spinner("Asserting claimed fact..."):
            answer = assert_fact(client, OTARI_VERIFICATION_MODEL, claim, not is_established)
        
        st.write("Fact-checking result:", answer["verdict"])
        st.write("Explanation:", answer["explanation"])
        
        with st.expander("Otari tool activity"):
            tool_calls = answer["tool_calls"]
            if tool_calls is None:
                st.info(
                    "No tool activity metadata returned. "
                    "This does not confirm whether a search occurred."
                )
            elif not tool_calls:
                st.info("Otari reported no tool calls.")
            else:
                st.caption(
                    "Inspect the results and any errors below. "
                    "A recorded call does not necessarily mean it succeeded."
                )
                st.json(tool_calls)

        st.write("Citations provided by the model:")
        if answer["citations"]:
            for citation in answer["citations"]:
                st.write(citation)
        else:
            st.info("No citations provided.")

    st.success("Analysis complete.")
