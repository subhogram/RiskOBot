import tempfile
import pandas as pd
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.llms import Ollama
from langchain_community.vectorstores import FAISS
from langchain.embeddings import OllamaEmbeddings

def build_knowledge_base(docs):
    # Split and embed the uploaded knowledge base documents
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    texts = []
    for doc in docs:
        splits = text_splitter.split_text(doc.page_content)
        texts.extend(splits)
    embeddings = OllamaEmbeddings()
    kb_vectorstore = FAISS.from_texts(texts, embedding=embeddings)
    return kb_vectorstore

def assess_evidence_with_kb(evidence_docs, kb_vectorstore):
    llm = Ollama(model="llama2")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    assessment = []
    for doc in evidence_docs:
        for evid_text in text_splitter.split_text(doc.page_content):
            # Retrieve relevant context from the knowledge base
            relevant_contexts = kb_vectorstore.similarity_search(evid_text, k=3)
            kb_context = "\n\n".join([c.page_content for c in relevant_contexts])
            prompt = (
                f"You are an information security auditor. "
                f"Given the following evidence snippet:\n\n{evid_text}\n\n"
                f"and the following policy/report context:\n\n{kb_context}\n\n"
                "1. Identify the type of evidence (e.g. DB log, password log, screenshot, config).\n"
                "2. Assess its compliance with the policy context and SOC2/CRI.\n"
                "3. Provide risk qualification, quantification, and a risk score (1-10), with a rationale.\n"
                "Response format: \n"
                "Evidence Type: <type>\n"
                "Compliance Assessment: <assessment>\n"
                "Risk Score: <score> (<rationale>)\n"
            )
            answer = llm(prompt)
            assessment.append({
                "evidence_snippet": evid_text[:200],
                "assessment": answer
            })
    return assessment

def generate_workbook(assessment):
    df = pd.DataFrame(assessment)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    df.to_excel(temp_file.name, index=False)
    return temp_file.name