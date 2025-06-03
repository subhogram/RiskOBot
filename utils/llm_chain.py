import tempfile
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.llms import Ollama
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import OllamaEmbeddings

# Instantiate reusable objects
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
embeddings = OllamaEmbeddings()
llm = Ollama(model="llama2")

def build_knowledge_base(docs):
    # Split and embed the uploaded knowledge base documents in batch
    texts = [split for doc in docs for split in text_splitter.split_text(doc.page_content)]
    kb_vectorstore = FAISS.from_texts(texts, embedding=embeddings)
    return kb_vectorstore

def _assess_single_evidence(evid_text, kb_vectorstore):
    relevant_contexts = kb_vectorstore.similarity_search(evid_text, k=3)
    kb_context = "\n\n".join([getattr(c, "page_content", str(c)) for c in relevant_contexts])
    prompt = (
        "You are an information security auditor.\n"
        f"Evidence snippet:\n{evid_text}\n\n"
        f"Policy/report context:\n{kb_context}\n\n"
        "1. Identify the type of evidence (e.g. DB log, password log, screenshot, config).\n"
        "2. Assess its compliance with the policy context and SOC2/CRI.\n"
        "3. Provide risk qualification, quantification, and a risk score (1-10), with a rationale.\n"
        "Response format:\n"
        "Evidence Type: <type>\n"
        "Compliance Assessment: <assessment>\n"
        "Risk Score: <score> (<rationale>)\n"
    )
    answer = llm(prompt)
    return {
        "evidence_snippet": evid_text[:200],
        "assessment": answer
    }

def assess_evidence_with_kb(evidence_docs, kb_vectorstore, max_workers=4):
    # Split all evidence texts first
    evid_texts = [split for doc in evidence_docs for split in text_splitter.split_text(doc.page_content)]
    # Parallelize assessment for faster processing
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(lambda evid: _assess_single_evidence(evid, kb_vectorstore), evid_texts))
    return results

def generate_workbook(assessment):
    df = pd.DataFrame(assessment)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    df.to_excel(temp_file.name, index=False)
    return temp_file.name