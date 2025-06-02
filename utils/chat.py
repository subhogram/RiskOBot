import streamlit as st
from langchain_community.llms import Ollama

def chat_with_bot(kb_vectorstore, assessment):
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []
    user_input = st.text_input("Ask a question about your audit:", key="chat_input")
    if st.button("Send", key="chat_send"):
        llm = Ollama(model="llama2")
        # Use both the knowledge base and the assessment for context
        kb_contexts = kb_vectorstore.similarity_search(user_input, k=3)
        kb_context = "\n\n".join([c.page_content for c in kb_contexts])
        assessment_context = "\n\n".join(a['assessment'] for a in assessment[:3])
        prompt = (
            f"You are an information security audit assistant. "
            f"User question: {user_input}\n\n"
            f"Policy/Report context:\n{kb_context}\n\n"
            f"Assessment context:\n{assessment_context}\n\n"
            f"Answer in a clear and concise way."
        )
        response = llm(prompt)
        st.session_state["chat_history"].append({"user": user_input, "bot": response})
    for chat in reversed(st.session_state["chat_history"]):
        st.write(f"**You:** {chat['user']}")
        st.write(f"**Bot:** {chat['bot']}")