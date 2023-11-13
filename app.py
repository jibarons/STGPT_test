
# Importing required packages
import streamlit as st
import openai
import uuid
import time

api_key = st.secrets["OPENAI_API"] 
client = openai.OpenAI(api_key=api_key)


# Model details
name="Testing Save's Data Assistant"
instructions="You are and assistant for a humanitarian organization. You will help program staff to solve data problems"
#MODEL = "gpt-3.5-turbo"
#MODEL = "gpt-3.5-turbo-0301"
#MODEL = "gpt-3.5-turbo-0613"
MODEL = "gpt-3.5-turbo-1106" # interpreter + retrieval
#MODEL = "gpt-3.5-turbo-16k"
#MODEL = "gpt-3.5-turbo-16k-0613"
#MODEL = "gpt-4"
#MODEL = "gpt-4-0613"
#MODEL = "gpt-4-0613"
#MODEL = "gpt-4-32k-0613"
#MODEL = "gpt-4-1106-preview" # interpreter + retrieval
#MODEL = "gpt-4-vision-preview"

# Initialize session state variables
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "run" not in st.session_state:
    st.session_state.run = {"status": None}

if "messages" not in st.session_state:
    st.session_state.messages = []

if "retry_error" not in st.session_state:
    st.session_state.retry_error = 0

if "file_id_list" not in st.session_state:
    st.session_state.file_id_list = []

# Create Streamlit page
st.set_page_config(page_title="Save's Analyst")

# Define funto upload file to openai (https://generativeai.pub/building-a-streamlit-q-a-app-using-openais-assistant-api-8193f718e7ed)
def upload_to_openai(filepath):
    """Upload a file to OpenAI and return its file ID."""
    with open(filepath, "rb") as file:
        response = openai.files.create(file=file.read(), purpose="assistants")
    return response.id

with st.sidebar:
    # Describe the bot
    st.title(name)
    st.subheader(MODEL)
    st.write(instructions)
    st.divider()

    # Upload files for retrieved
    uploaded_file = st.file_uploader(label="Add files for retrieval")
    ## Write file into path
    if uploaded_file is not None:
        with open(f"{uploaded_file.name}", "wb") as f:
            f.write(uploaded_file.getbuffer())
        # Create file for openai (read binary)
        file = client.files.create(
            file=open(f"{uploaded_file.name}", "rb"),
            purpose='assistants'
        )
        # adding multiple files to the assistant (not working)
        additional_file_id = upload_to_openai(f"{uploaded_file.name}")
        st.session_state.file_id_list.append(additional_file_id)
        st.write(f"Additional File ID: {additional_file_id}")
    st.divider()

    # Credits
    st.markdown("Base code from Mark Craddock](https://github.com/tractorjuice/STGPT)", unsafe_allow_html=False)
    st.markdown(st.session_state.session_id)

with st.container():
    st.write("Session will start once a file is uploaded") # temp, need fix
    if "assistant" not in st.session_state:
        openai.api_key = st.secrets["OPENAI_API"]
        
        # Load the previously created assistant
        #st.session_state.assistant = openai.beta.assistants.retrieve(st.secrets["OPENAI_ASSISTANT"])  
        st.session_state.assistant = openai.beta.assistants.create(
            name=name, instructions=instructions,model=MODEL,
            tools=[{"type": "code_interpreter"}, {"type": "retrieval"}],
            file_ids=[file.id]
        )

        # Adding multiple files to an existing assistant (not working)
        # for file_id in st.session_state.file_id_list:
        #         st.sidebar.write(file_id)
        #         # Associate files with the assistant
        #         assistant_file = client.beta.assistants.files.create(
        #             assistant_id=st.session_state.assistant, 
        #             file_id=file_id
        #         )

        # Create a new thread for this session
        st.session_state.thread = client.beta.threads.create(
            metadata={
                'session_id': st.session_state.session_id,
            }
        )

    # If the run is completed, display the messages
    elif hasattr(st.session_state.run, 'status') and st.session_state.run.status == "completed":
        # Retrieve the list of messages
        st.session_state.messages = client.beta.threads.messages.list(
            thread_id=st.session_state.thread.id
        )

        for thread_message in st.session_state.messages.data:
            for message_content in thread_message.content:
                # Access the actual text content
                message_content = message_content.text
                annotations = message_content.annotations
                citations = []
                
                # Iterate over the annotations and add footnotes
                for index, annotation in enumerate(annotations):
                    # Replace the text with a footnote
                    message_content.value = message_content.value.replace(annotation.text, f' [{index}]')
                
                    # Gather citations based on annotation attributes
                    if (file_citation := getattr(annotation, 'file_citation', None)):
                        cited_file = client.files.retrieve(file_citation.file_id)
                        citations.append(f'[{index}] {file_citation.quote} from {cited_file.filename}')
                    elif (file_path := getattr(annotation, 'file_path', None)):
                        cited_file = client.files.retrieve(file_path.file_id)
                        citations.append(f'[{index}] Click <here> to download {cited_file.filename}')
                        # Note: File download functionality not implemented above for brevity

                # Add footnotes to the end of the message before displaying to user
                message_content.value += '\n' + '\n'.join(citations)

        # Display messages
        for message in reversed(st.session_state.messages.data):
            if message.role in ["user", "assistant"]:
                with st.chat_message(message.role):
                    for content_part in message.content:
                        message_text = content_part.text.value
                        st.markdown(message_text)

    if prompt := st.chat_input("How can I help you?"):
        with st.chat_message('user'):
            st.write(prompt)

        # Add message to the thread
        st.session_state.messages = client.beta.threads.messages.create(
            thread_id=st.session_state.thread.id,
            role="user",
            content=prompt
        )

        # Do a run to process the messages in the thread
        st.session_state.run = client.beta.threads.runs.create(
            thread_id=st.session_state.thread.id,
            assistant_id=st.session_state.assistant.id,
        )
        if st.session_state.retry_error < 3:
            time.sleep(1) # Wait 1 second before checking run status
            st.rerun()
                        
    # Check if 'run' object has 'status' attribute
    if hasattr(st.session_state.run, 'status'):
        # Handle the 'running' status
        if st.session_state.run.status == "running":
            with st.chat_message('assistant'):
                st.write("Thinking ......")
            if st.session_state.retry_error < 3:
                time.sleep(1)  # Short delay to prevent immediate rerun, adjust as needed
                st.rerun()

        # Handle the 'failed' status
        elif st.session_state.run.status == "failed":
            st.session_state.retry_error += 1
            with st.chat_message('assistant'):
                if st.session_state.retry_error < 3:
                    st.write("Run failed, retrying ......")
                    time.sleep(3)  # Longer delay before retrying
                    st.rerun()
                else:
                    st.error("FAILED: The OpenAI API is currently processing too many requests. Please try again later ......")

        # Handle any status that is not 'completed'
        elif st.session_state.run.status != "completed":
            # Attempt to retrieve the run again, possibly redundant if there's no other status but 'running' or 'failed'
            st.session_state.run = client.beta.threads.runs.retrieve(
                thread_id=st.session_state.thread.id,
                run_id=st.session_state.run.id,
            )
            if st.session_state.retry_error < 3:
                time.sleep(3)
                st.rerun()
