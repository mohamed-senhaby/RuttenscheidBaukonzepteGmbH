import streamlit as st
import google.genai as genai
import tempfile
import os
from datetime import datetime

# 1. Configure the Page
st.set_page_config(page_title="Gemini Chatbot", page_icon="🤖")
st.title("🤖 Chat with Mohamed")

# 2. Setup Gemini API
# SECURITY NOTE: Never commit your API Key to GitHub. 
# Use st.secrets or input it via sidebar for production.
api_key = st.secrets.get("api_key", "")

if api_key:
    client = genai.Client(api_key=api_key)
    
    # Initialize chat sessions
    if "chats" not in st.session_state:
        st.session_state.chats = {
            "chat_1": {
                "name": "Chat 1",
                "messages": [],
                "created": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
        }
        st.session_state.current_chat = "chat_1"
        st.session_state.chat_counter = 1
    
    # Sidebar: New Chat Button
    st.sidebar.title("💬 Conversations")
    if st.sidebar.button("➕ New Chat", use_container_width=True):
        st.session_state.chat_counter += 1
        new_chat_id = f"chat_{st.session_state.chat_counter}"
        st.session_state.chats[new_chat_id] = {
            "name": f"Chat {st.session_state.chat_counter}",
            "messages": [],
            "created": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        st.session_state.current_chat = new_chat_id
        st.rerun()
    
    st.sidebar.divider()
    
    # Display all chats in sidebar
    for chat_id, chat_data in st.session_state.chats.items():
        is_current = chat_id == st.session_state.current_chat
        button_label = f"{'🟢' if is_current else '⚪'} {chat_data['name']}"
        
        col1, col2 = st.sidebar.columns([4, 1])
        with col1:
            if st.button(button_label, key=f"btn_{chat_id}", use_container_width=True):
                st.session_state.current_chat = chat_id
                st.rerun()
        with col2:
            if st.button("🗑️", key=f"del_{chat_id}"):
                if len(st.session_state.chats) > 1:
                    del st.session_state.chats[chat_id]
                    # Switch to first available chat
                    st.session_state.current_chat = list(st.session_state.chats.keys())[0]
                    st.rerun()
    
    st.sidebar.divider()
    
    # Get current chat messages
    current_chat = st.session_state.chats[st.session_state.current_chat]
    messages = current_chat["messages"]
    
    # File uploader in main area (above chat history)
    uploaded_file = st.file_uploader(
        "📎 Upload a file (images, PDFs, text files, etc.)",
        type=['png', 'jpg', 'jpeg', 'gif', 'pdf', 'txt', 'doc', 'docx', 'csv'],
        key=f"uploader_{st.session_state.current_chat}"
    )

    # Display History
    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Handle Input
    if prompt := st.chat_input("What's on your mind?"):
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        messages.append({"role": "user", "content": prompt})

        # 6. Generate Response
        try:
            # Create a spinner while the model thinks
            with st.spinner("Thinking..."):
                contents = []
                temp_file_path = None
                
                # Handle File Upload
                if uploaded_file:
                    # 1. Save uploaded file to a temporary file on disk
                    # We create a temp file with the correct extension (e.g., .pdf)
                    # delete=False is required so we can close it and let Gemini read it
                    suffix = f".{uploaded_file.name.split('.')[-1]}"
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(uploaded_file.getvalue())
                        temp_file_path = tmp.name
                    
                    # 2. Upload the file to Gemini using the disk path
                    # FIX: Use 'file=' parameter, not 'path='
                    uploaded_genai_file = client.files.upload(file=temp_file_path)
                    
                    # 3. Add to contents list
                    contents = [uploaded_genai_file, prompt]
                else:
                    contents = [prompt]
                
                # 4. Generate content
                response = client.models.generate_content(
                    model='gemini-2.5-flash-lite',
                    contents=contents
                )
                
                # 5. Clean up: Delete the temp file from your disk
                if temp_file_path and os.path.exists(temp_file_path):
                    os.remove(temp_file_path)

            # Display assistant response
            with st.chat_message("assistant"):
                st.markdown(response.text)
            
            # Add assistant response to history
            messages.append({"role": "assistant", "content": response.text})
            
            # Update chat name with first message (if it's still default)
            if current_chat["name"].startswith("Chat ") and len(messages) == 2:
                # Use first 30 chars of first user message as chat name
                current_chat["name"] = prompt[:30] + ("..." if len(prompt) > 30 else "")
            
        except Exception as e:
            st.error(f"An error occurred: {e}")
else:
    st.warning("Please enter your API Key to start.")