import os
import shutil
import streamlit as st
from utils.file_handlers import save_and_load_files
from utils.llm_chain import build_knowledge_base, assess_evidence_with_kb, generate_workbook
from utils.chat import chat_with_bot
import base64


# ControlTester 3000 - Cyber Risk Audit Bot
# This is a Streamlit app for a Cyber Risk Audit Bot that allows users to upload policies and evidence files,
# train a knowledge base, assess evidence against the knowledge base, and generate an audit workbook.


VECTORSTORE_PATH = "saved_kb_vectorstore"

st.set_page_config(page_title="Control Risk Audit Bot", layout="wide")
with open("kpmg_logo.png", "rb") as logo_file:
    logo_base64 = base64.b64encode(logo_file.read()).decode("utf-8")

st.markdown(
    f"""
    <div style="display: flex; align-items: center; justify-content: flex-end; padding: 12px 0 18px 0; border-bottom: 1px solid #eaeaea;">
        <img src="data:image/png;base64,{logo_base64}" alt="Logo" style="height:48px;">
    </div>
    """,
    unsafe_allow_html=True
)

st.title("🤖 Control Risk Audit Bot")
st.markdown("Welcome to your Control risk assistant. Start by uploading your policies and evidence files below.")



# --- Load saved bot at app start ---
if os.path.exists(VECTORSTORE_PATH) and not st.session_state.get('kb_ready', False):
    from langchain_community.vectorstores import FAISS
    from langchain_community.embeddings import OllamaEmbeddings
    st.session_state['kb_vectorstore'] = FAISS.load_local(
        VECTORSTORE_PATH,
        OllamaEmbeddings(),
        allow_dangerous_deserialization=True
    )
    st.session_state['kb_ready'] = True
    st.session_state['kb_loaded_from_saved'] = True



# --- Step 1: Upload Knowledge Base Documents ---
with st.expander("1️⃣ Upload Knowledge Base Documents", expanded=True):
    policy_files = st.file_uploader(
        "Upload Information Security Policies, SOC 2 Reports, or CRI Profiles (PDF, TXT, CSV, XLSX)",
        type=["pdf", "txt", "csv", "xlsx"], accept_multiple_files=True
    )

    # --- Training & Bot Controls ---
    if 'kb_ready' not in st.session_state:
        st.session_state['kb_ready'] = False
    if 'assessment_done' not in st.session_state:
        st.session_state['assessment_done'] = False
    if 'kb_loaded_from_saved' not in st.session_state:
        st.session_state['kb_loaded_from_saved'] = False
    if 'bot_trained_success' not in st.session_state:
        st.session_state['bot_trained_success'] = False

    # --- Load saved bot at app start ---
    if os.path.exists(VECTORSTORE_PATH) and not st.session_state.get('kb_ready', False):
        from langchain_community.vectorstores import FAISS
        from langchain.embeddings import OllamaEmbeddings
        st.session_state['kb_vectorstore'] = FAISS.load_local(
            VECTORSTORE_PATH,
            OllamaEmbeddings(),
            allow_dangerous_deserialization=True
        )

        st.session_state['kb_ready'] = True
        st.session_state['kb_loaded_from_saved'] = True
        st.session_state['bot_trained_success'] = True

     # --- Dynamic Button States ---
    train_disabled = not (policy_files and len(policy_files) > 0)
    save_disabled = not st.session_state.get('bot_trained_success', False)
    delete_disabled = not os.path.exists(VECTORSTORE_PATH)

    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        train_btn = st.button(
            "🔄 Train Bot",
            help="Train bot on uploaded knowledge base",
            disabled=train_disabled,
            key="train_btn"
        )
    with col2:
        save_btn = st.button(
            "💾 Save Bot",
            disabled=save_disabled,
            help="Save the current trained bot",
            key="save_btn"
        )
    with col3:
        delete_btn = st.button(
            "🗑️ Delete Saved Bot",
            disabled=delete_disabled,
            help="Delete the previously saved bot",
            key="delete_btn"
        )

   # Train bot on KB
    if train_btn:
        with st.spinner("Processing and indexing knowledge base..."):
            kb_docs = save_and_load_files(policy_files)
            kb_vectorstore = build_knowledge_base(kb_docs)            
            st.session_state['kb_vectorstore'] = kb_vectorstore
            st.session_state['kb_ready'] = True
            st.session_state['bot_trained_success'] = True  # <-- enable Save on next rerun!
            st.session_state['bot_saved'] = False  # Not yet saved after new training
            st.session_state['kb_loaded_from_saved'] = False
        # Optionally force a rerun so Save enables immediately
        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()

    # Save trained bot
    if save_btn and not save_disabled:
        if 'kb_vectorstore' in st.session_state and st.session_state['kb_vectorstore'] is not None:
            st.session_state['kb_vectorstore'].save_local(VECTORSTORE_PATH)
            st.success("💾 Trained bot saved successfully!")
            st.session_state['bot_trained_success'] = False
            st.session_state['bot_saved'] = True
        else:
            st.error("No trained bot to save. Please train the bot first.")
        
        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()

    # Delete previous trained bot
    if delete_btn and not delete_disabled:
        if os.path.exists(VECTORSTORE_PATH):
            shutil.rmtree(VECTORSTORE_PATH)
            st.success("🗑️ Previous trained bot deleted successfully.")
            st.session_state['kb_ready'] = False
            st.session_state['kb_vectorstore'] = None
            st.session_state['bot_trained_success'] = False
            st.session_state['bot_saved'] = False
            st.session_state['kb_loaded_from_saved'] = False
        else:
            st.info("No saved trained bot found to delete.")

        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()

    # Show persistent training success message
    if st.session_state.get('bot_trained_success', False):
        st.success("✅ Knowledge base trained and ready!")
    elif st.session_state.get('bot_saved', False):
        st.info("💾 A trained bot is saved, ready for use.")
    elif st.session_state.get('kb_loaded_from_saved', False):
        st.warning("💽 A saved trained bot is loaded and ready for use.")
    else:
        st.warning("🚫 No trained bot loaded. Please train or load a saved bot.")

# --- Step 2: Upload Evidence Files ---
with st.expander("2️⃣ Upload Evidence Files", expanded=True):
    evidence_files = st.file_uploader(
        "Upload Evidence (Logs, Configs, Screenshots - PDF, TXT, CSV, XLSX, JPEG)",
        type=["pdf", "txt", "csv", "xlsx", "jpeg", "jpg"], accept_multiple_files=True
    )
    evidence_ready = st.session_state.get('kb_ready') and (evidence_files is not None and len(evidence_files) > 0)
    process_btn = st.button("🧮 Process Evidence & Generate Workbook", disabled=not evidence_ready, help="Assess uploaded evidence using the knowledge base and generate an audit workbook.")

    if process_btn and evidence_ready:
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
        st.success("✅ Evidence processed! Audit workbook ready.")
        st.info("You can now download the audit workbook and chat with the bot.")  

# --- Step 3: Download and Chat ---
if st.session_state.get('assessment_done'):
    with st.expander("3️⃣ Download Audit Workbook & Chat with Bot", expanded=True):
        st.subheader("Download Cyber Risk Audit Workbook")
        with open(st.session_state['workbook_path'], "rb") as f:
            st.download_button("⬇️ Download Audit Workbook", f, file_name="CyberRisk_Audit_Workbook.xlsx")
        st.subheader("Chat with the Audit Bot")
        chat_with_bot(st.session_state['kb_vectorstore'], st.session_state['assessment'])
else:
    with st.expander("3️⃣ Download Audit Workbook & Chat with Bot", expanded=False):
        st.info("Process evidence first to unlock download and chat features.")