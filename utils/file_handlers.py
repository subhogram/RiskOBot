import os
import tempfile
from langchain_community.document_loaders import (
    UnstructuredPDFLoader,
    UnstructuredFileLoader,
)

def save_temp_file(file):
    suffix = file.name.split(".")[-1]
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix="."+suffix)
    temp_file.write(file.read())
    temp_file.close()
    return temp_file.name

def save_and_load_files(files):
    docs = []
    if files:
        for file in files:
            temp_path = save_temp_file(file)
            ext = os.path.splitext(temp_path)[-1].lower()
            if ext == ".pdf":
                loader = UnstructuredPDFLoader(temp_path)
            elif ext in [".txt", ".csv", ".xlsx", ".jpeg", ".jpg"]:
                loader = UnstructuredFileLoader(temp_path)
            else:
                continue
            docs.extend(loader.load())
            os.unlink(temp_path)
    return docs