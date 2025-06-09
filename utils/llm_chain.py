import os
import time
import tempfile
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.llms import Ollama
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import OllamaEmbeddings
import logging

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Instantiate reusable LangChain components
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=512,
    chunk_overlap=64,
    length_function=len,
    add_start_index=True
)
embeddings = OllamaEmbeddings(model="llama2")  # Ensure faiss-gpu is installed for GPU usage
llm = Ollama(model="llama2")

# ----------------- KNOWLEDGE BASE BUILDER -----------------

def build_knowledge_base(docs):
    start = time.time()
    texts = []
    for i, doc in enumerate(docs):
        try:
            if not doc.page_content.strip():
                logger.warning(f"Document {i} is empty and skipped.")
                continue
            splits = text_splitter.split_text(doc.page_content)
            texts.extend(splits)
            logger.info(f"Document {i} split into {len(splits)} chunks.")
        except Exception as e:
            logger.error(f"Error processing document {i}: {e}")

    if not texts:
        raise ValueError("No valid content found in input documents.")

    logger.info(f"Embedding {len(texts)} chunks...")
    try:
        kb_vectorstore = FAISS.from_texts(texts, embedding=embeddings)
        logger.info(f"Vector store built successfully with {kb_vectorstore.index.ntotal} vectors.")
    except Exception as e:
        logger.critical(f"Vector store creation failed: {e}")
        raise

    logger.info(f"Knowledge base built in {time.time() - start:.2f} seconds.")
    return kb_vectorstore

# ----------------- SINGLE EVIDENCE ASSESSMENT -----------------

def _assess_single_evidence(evid_text, kb_vectorstore, chunk_index=0, doc_index=0):
    try:
        relevant_contexts = kb_vectorstore.similarity_search(evid_text, k=3)
        kb_context = "\n\n".join([getattr(c, "page_content", str(c)) for c in relevant_contexts])

        prompt = (
            "You are an information security auditor.\n"
            f"Evidence snippet:\n{evid_text}\n\n"
            f"Policy/report context:\n{kb_context}\n\n"
            "1. Identify the type of evidence (e.g. DB log, password log, screenshot, config).\n"
            "2. Assess its compliance with the policy context and SOC2/CRI.\n"
            "3. Provide the control statement against which the evidence is tested.\n"
            "4. if the evidence is not compliant, return 'Non-Compliant',log entry where it fails the control and rationale as to why it fails the control statement.\n"
            "5. If compliant, return 'Compliant' with no further details.\n"
            "6. Suggest improvements and reremedy if applicable. If remedy measures are already present and evident in logs, point those out.\n\n"

            "Provide response in below format:\n"
            "Control Statement: <control statement>\n"
            "Assessment: <Compliant/Non-Compliant>\n"
            "Evidence Type: <evidence type>\n"           
            "Log Entry: <if Non-Compliant, log entry where it fails>\n"
            "Rationale: <if Non-Compliant, rationale for failure>\n"
            "Improvements: <if applicable, suggestions for improvement/remedy measures if Non-Compliant>\n"
        )
        answer = llm(prompt)
        return {            
            "assessment": answer
        }
    except Exception as e:
        logger.error(f"Assessment failed for chunk {chunk_index} (doc {doc_index}): {e}")
        return {
            "assessment": f"Error: {e}"
        }

# ----------------- PARALLEL EVIDENCE ASSESSMENT -----------------

def assess_evidence_with_kb(evidence_docs, kb_vectorstore, max_workers=4):
    start = time.time()
    evid_texts, chunk_origin = [], []

    for i, doc in enumerate(evidence_docs):
        try:
            if not doc.page_content.strip():
                logger.warning(f"Evidence document {i} is empty and skipped.")
                continue
            splits = text_splitter.split_text(doc.page_content)
            evid_texts.extend(splits)
            chunk_origin.extend([i] * len(splits))
            logger.info(f"Evidence document {i} split into {len(splits)} chunks.")
        except Exception as e:
            logger.error(f"Error splitting evidence document {i}: {e}")

    if not evid_texts:
        logger.warning("No valid evidence found.")
        return []

    logger.info(f"Assessing {len(evid_texts)} evidence chunks using {max_workers} threads...")
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_assess_single_evidence, evid_texts[i], kb_vectorstore, i, chunk_origin[i])
            for i in range(len(evid_texts))
        ]
        for future in as_completed(futures):
            results.append(future.result())

    logger.info(f"Assessment completed in {time.time() - start:.2f} seconds.")
    return results

# ----------------- WORKBOOK EXPORT -----------------

def generate_workbook(assessment, filename_prefix="audit_assessment"):
    start = time.time()
    if not assessment or not isinstance(assessment[0], dict):
        logger.warning("No valid assessment data to write.")
        return None

    try:
        df = pd.DataFrame(assessment)
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx", prefix=filename_prefix)
        df.to_excel(temp_file.name, index=False)
        size_kb = os.path.getsize(temp_file.name) / 1024
        logger.info(f"Workbook saved: {temp_file.name} ({size_kb:.2f} KB) in {time.time() - start:.2f} sec")
        return temp_file.name
    except Exception as e:
        logger.critical(f"Failed to generate Excel workbook: {e}")
        return None
