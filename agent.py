import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
import pdfplumber
import io
from langchain.llms import Ollama
from langchain.schema import Document

# ========== UTILITY FUNCTIONS ==========

def extract_text_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for i, page in enumerate(pdf.pages):
            if i > 20:  # limit for safety
                break
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

def extract_text_from_txt(file):
    return file.read().decode("utf-8", errors="ignore")

def extract_text_from_csv(file):
    df = pd.read_csv(file)
    return df.to_csv(index=False)

def extract_text_from_xlsx(file):
    df = pd.read_excel(file)
    return df.to_csv(index=False)

def extract_text_from_image(file):
    image = Image.open(file)
    text = pytesseract.image_to_string(image)
    return text

def extract_text(file, filetype):
    try:
        if filetype == "pdf":
            return extract_text_from_pdf(file)
        elif filetype == "txt":
            return extract_text_from_txt(file)
        elif filetype == "csv":
            return extract_text_from_csv(file)
        elif filetype == "xlsx":
            return extract_text_from_xlsx(file)
        elif filetype in ["jpg", "jpeg", "png"]:
            return extract_text_from_image(file)
    except Exception as e:
        return f"Error extracting text: {e}"
    return ""

def get_all_text(files):
    texts = []
    for file in files:
        name = file.name
        ext = name.split(".")[-1].lower()
        text = extract_text(file, ext)
        texts.append({"filename": name, "content": text})
    return texts

# ========== LLM LOGIC ==========

def get_ollama_llm():
    return Ollama(model="llama2")

def extract_policies(policy_texts, llm):
    full_policy = "\n\n".join([p["content"] for p in policy_texts])
    prompt = (
        "Extract a list of all unique security policies with IDs or titles from the following documents. "
        "List them in the format: POLICY_ID or TITLE: Policy description."
        "\n\nDocuments:\n"
        f"{full_policy}\n\nList of Policies:"
    )
    response = llm(prompt)
    policies = []
    for line in response.splitlines():
        if ":" in line:
            pid, desc = line.split(":", 1)
            pid = pid.strip()
            desc = desc.strip()
            if pid and desc:
                policies.append({"id": pid, "desc": desc})
    return policies

def match_evidence_to_policy(evidence, policies, llm):
    prompt = (
        "Given the following evidence content, determine which policy from the list below is most relevant. "
        "Respond only with the POLICY_ID or TITLE.\n\n"
        f"Evidence:\n{evidence}\n\n"
        "Policies:\n" +
        "\n".join([f"{p['id']}: {p['desc']}" for p in policies])
    )
    match = llm(prompt).strip().split("\n")[0]
    for p in policies:
        if match.lower() in p["id"].lower() or match.lower() in p["desc"].lower():
            return p
    return policies[0] if policies else None

def compliance_verdict(policy, evidence, llm):
    prompt = (
        f"Security Policy: {policy['id']}: {policy['desc']}\n"
        f"Evidence File Content: {evidence}\n\n"
        "Based on the evidence, is the policy control in compliance? "
        "Give a verdict: 'Compliant', 'Non-Compliant', or 'Partial', and a short explanation."
    )
    verdict = llm(prompt)
    return verdict

def answer_on_evidence_policy(policy, evidence, user_question, llm):
    prompt = (
        f"Security Policy: {policy['id']}: {policy['desc']}\n"
        f"Evidence File Content: {evidence}\n\n"
        f"User question: {user_question}\n\n"
        "Answer only using the policy and evidence above."
    )
    answer = llm(prompt)
    return answer

# ========== STREAMLIT UI ==========

st.set_page_config(page_title="Security Control Audit Bot", layout="wide")
st.title("🔒 Security Control Audit Bot")

st.sidebar.header("Upload Files")
policy_files = st.sidebar.file_uploader("Upload Policy Documents", type=["pdf", "txt", "csv", "xlsx"], accept_multiple_files=True)
evidence_files = st.sidebar.file_uploader("Upload Evidence Files (logs, screenshots)", type=["pdf", "txt", "csv", "xlsx", "jpg", "jpeg", "png"], accept_multiple_files=True)
run_audit = st.sidebar.button("Run Audit")
if st.sidebar.button("Reset Chat"):
    st.session_state["last_bot_reply"] = None
    # Don't reset evidence selection so selector stays visible

if "last_bot_reply" not in st.session_state:
    st.session_state["last_bot_reply"] = None
if "selected_evidence" not in st.session_state:
    st.session_state["selected_evidence"] = None
if "evidence_policy_map" not in st.session_state:
    st.session_state["evidence_policy_map"] = {}
if "workbook_bytes" not in st.session_state:
    st.session_state["workbook_bytes"] = None
if "dataframe_results" not in st.session_state:
    st.session_state["dataframe_results"] = None

llm = get_ollama_llm()

if run_audit:
    policy_texts = get_all_text(policy_files) if policy_files else []
    evidence_texts = get_all_text(evidence_files) if evidence_files else []

    policies = extract_policies(policy_texts, llm)
    evidence_policy_map = {}
    results = []
    for evidence in evidence_texts:
        matched_policy = match_evidence_to_policy(evidence["content"], policies, llm)
        verdict = compliance_verdict(matched_policy, evidence["content"], llm)
        status = "Unknown"
        v_lower = verdict.lower()
        if "non-compliant" in v_lower:
            status = "Non-Compliant"
        elif "compliant" in v_lower:
            status = "Compliant"
        elif "partial" in v_lower:
            status = "Partial"
        evidence_policy_map[evidence["filename"]] = matched_policy
        results.append({
            "Evidence File": evidence["filename"],
            "Policy": f"{matched_policy['id']}",
            "Status": status,
            "LLM Verdict": verdict[:300] + ("..." if len(verdict) > 300 else "")
        })
    st.session_state["evidence_policy_map"] = evidence_policy_map

    df_results = pd.DataFrame(results)
    st.session_state["dataframe_results"] = df_results

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_results.to_excel(writer, index=False, sheet_name='Audit Results')
    st.session_state["workbook_bytes"] = output.getvalue()

    evidence_files_list = [e["filename"] for e in evidence_texts]
    if evidence_files_list:
        st.session_state["evidence_files_list"] = evidence_files_list
        if st.session_state["selected_evidence"] not in evidence_files_list:
            st.session_state["selected_evidence"] = evidence_files_list[0]
    else:
        st.session_state["evidence_files_list"] = []
        st.session_state["selected_evidence"] = None

if st.session_state.get("dataframe_results") is not None:
    st.header("Audit Results")
    st.dataframe(st.session_state["dataframe_results"])
    if st.session_state.get("workbook_bytes") is not None:
        st.download_button(
            "Download Audit Workbook",
            data=st.session_state["workbook_bytes"],
            file_name="audit_results.xlsx"
        )

evidence_files_list = st.session_state.get("evidence_files_list", [])
if evidence_files_list:
    st.markdown("### Select an Evidence File to Chat About")
    sel_idx = 0
    if st.session_state["selected_evidence"] in evidence_files_list:
        sel_idx = evidence_files_list.index(st.session_state["selected_evidence"])
    selected_evidence = st.selectbox("Evidence Files", evidence_files_list, index=sel_idx)
    st.session_state["selected_evidence"] = selected_evidence

st.markdown("## 💬 Audit Chat with the Bot")

if st.session_state.get("selected_evidence"):
    evidence_filename = st.session_state["selected_evidence"]
    evidence_content = ""
    matched_policy = st.session_state["evidence_policy_map"].get(evidence_filename)
    if evidence_files:
        for file in evidence_files:
            if file.name == evidence_filename:
                ext = file.name.split(".")[-1].lower()
                evidence_content = extract_text(file, ext)
                break
    if matched_policy:
        st.info(f"Chatting about evidence file **{evidence_filename}** mapped to policy **{matched_policy['id']}**.")
    else:
        st.warning("Policy not matched. Please rerun audit.")
else:
    evidence_content = ""
    matched_policy = None
    st.warning("Please run an audit and select an evidence file.")

# Only show the last bot reply and last user question (clear previous on new send)
user_input = st.text_input("Type your question about this evidence & policy...", key="chatbox")
send_btn = st.button("Send")
if matched_policy and evidence_content and send_btn and user_input:
    # Clear previous reply and show only the new exchange
    st.session_state["last_bot_reply"] = None
    user_question = user_input
    answer = answer_on_evidence_policy(matched_policy, evidence_content, user_question, llm)
    st.session_state["last_bot_reply"] = (user_question, answer)

if st.session_state["last_bot_reply"]:
    user_question, bot_answer = st.session_state["last_bot_reply"]
    st.write(f"**You:** {user_question}")
    st.write(f"**Bot:** {bot_answer}")