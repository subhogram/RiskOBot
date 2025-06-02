import streamlit as st
from utils.file_handlers import save_and_load_files
from utils.llm_chain import build_knowledge_base, assess_evidence_with_kb, generate_workbook
from utils.chat import chat_with_bot

st.set_page_config(page_title="Cyber Risk Audit Bot", layout="wide")
st.title("Cyber Risk Audit Bot")

st.header("1. Upload Knowledge Base Documents")
policy_files = st.file_uploader(
    "Upload Information Security Policies, SOC 2 Reports, CRI Profile (PDF, TXT, CSV, XLSX)",
    type=["pdf", "txt", "csv", "xlsx"], accept_multiple_files=True
)

st.header("2. Upload Evidence Files")
evidence_files = st.file_uploader(
    "Upload Evidence (Logs, Configs, Screenshots - PDF, TXT, CSV, XLSX, JPEG)",
    type=["pdf", "txt", "csv", "xlsx", "jpeg", "jpg"], accept_multiple_files=True
)

if 'kb_ready' not in st.session_state:
    st.session_state['kb_ready'] = False
if 'assessment_done' not in st.session_state:
    st.session_state['assessment_done'] = False

# Step 1: Train vector/store on uploaded policies, SOC2, CRI
if st.button("Train Bot on Knowledge Base"):
    with st.spinner("Processing and indexing knowledge base..."):
        kb_docs = save_and_load_files(policy_files)
        kb_vectorstore = build_knowledge_base(kb_docs)
        st.session_state['kb_vectorstore'] = kb_vectorstore
        st.session_state['kb_ready'] = True
    st.success("Knowledge base trained and ready!")

# Step 2: Process evidence files using trained vectorstore (knowledge base)
if st.session_state.get('kb_ready') and st.button("Process Evidence Files and Generate Audit Workbook"):
    with st.spinner("Assessing evidence using knowledge base..."):
        evidence_docs = save_and_load_files(evidence_files)
        assessment = assess_evidence_with_kb(
            evidence_docs,
            st.session_state['kb_vectorstore']
        )
        workbook_path = generate_workbook(assessment)
        st.session_state['assessment'] = assessment
        st.session_state['workbook_path'] = workbook_path
        st.session_state['assessment_done'] = True
    st.success("Evidence processed! Audit workbook ready.")

if st.session_state.get('assessment_done'):
    st.header("3. Download Cyber Risk Audit Workbook")
    with open(st.session_state['workbook_path'], "rb") as f:
        st.download_button("Download Audit Workbook", f, file_name="CyberRisk_Audit_Workbook.xlsx")

    st.header("4. Chat with the Audit Bot")
    chat_with_bot(st.session_state['kb_vectorstore'], st.session_state['assessment'])