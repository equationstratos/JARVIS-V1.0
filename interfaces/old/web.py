import streamlit as st
import os
import asyncio
from core.orchestrator import Orchestrator

st.set_page_config(
    page_title="JARVIS AI Ecosystem",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Style Customization
st.markdown("""
    <style>
    .stApp {
        background-color: #0f172a;
        color: #f8fafc;
    }
    .stChatMessage {
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 10px;
    }
    .stSidebar {
        background-color: #1e293b;
    }
    </style>
    """, unsafe_allow_html=True)

# Async helper
def run_async(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

if 'orchestrator' not in st.session_state:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    agents_dir = os.path.join(project_root, "agents/configs")
    st.session_state.orchestrator = Orchestrator(agents_dir)
    st.session_state.history = []

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/iron-man.png", width=80)
    st.title("JARVIS Config")
    
    st.divider()
    
    available_models = [
        "gemini/gemini-3.1-flash-lite-preview",
        "gemini/gemini-flash-latest",
        "gemini/gemini-pro-latest",
        "openai/gpt-4o",
    ]
    
    selected_model = st.selectbox(
        "Modèle actif",
        options=available_models,
        index=0
    )
    st.session_state.orchestrator.set_override_model(selected_model)

    st.divider()
    st.subheader("👥 Agents Actifs")
    for agent_name in st.session_state.orchestrator.agents.keys():
        st.caption(f"✓ {agent_name}")
    
    if st.button("Réinitialiser le Chat"):
        st.session_state.history = []
        st.rerun()

# Main Chat Interface
st.title("🤖 JARVIS Ecosystem")
st.caption("Assistant IA Modulaire & Agentique")

# Display History
for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# User Input
if prompt := st.chat_input("Que puis-je faire pour vous ?"):
    # Append user message
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Assistant response
    with st.chat_message("assistant"):
        with st.spinner("JARVIS réfléchit..."):
            try:
                # We pass the history excluding the last message (current user prompt)
                response = run_async(
                    st.session_state.orchestrator.route(prompt, st.session_state.history[:-1])
                )
                st.markdown(response)
                st.session_state.history.append({"role": "assistant", "content": response})
            except Exception as e:
                st.error(f"Erreur d'orchestration : {str(e)}")
