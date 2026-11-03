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


SYSTEM_PROMPT = "You are a concise, friendly truth-seeking journalist."

client = OtariClient(api_base=OTARI_URL, 
                    api_key=OTARI_API_KEY)

st.title("Otari Fact Checker")
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

        st.write("Is an established fact:", established)

        with st.spinner("Checking whether web search is needed..."):
            answer = assert_fact(client, OTARI_MODEL, claim, not established)
        
        st.write("Fact-checking result:", answer["verdict"])
        st.write("Explanation:", answer["explanation"])
        st.write("Searched:", answer["searched"])
        if answer["searched"]:
            st.write("Citations:", answer["citations"][0])

    st.success("Analysis complete.")
