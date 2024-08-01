from openai import OpenAI
import shelve
from dotenv import load_dotenv
import os
import time
import logging

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")
client = OpenAI(api_key=OPENAI_API_KEY)


# def upload_file(path):
#     # Upload a file with an "assistants" purpose
#     file = client.files.create(
#         file=open("../../data/t3a_knowledge.txt", "rb"), purpose="assistants"
#     )


def create_assistant(file):
    """
    You currently cannot set the temperature for Assistant via the API.
    """
    assistant = client.beta.assistants.create(
        name="Zowobo",
        instructions="Zowobo is a WhatsApp assistant designed to give Haitians access to AI technology. It can listen to voice messages and respond in Haitian Creole. Zowobo is here to answer questions, provide information, and help with various issues. If there's something it doesn't know, it will clearly say so and suggest seeking help elsewhere. Zowobo always tries to give simple, useful, and easy-to-understand responses. It has a bit of a sense of humor too, but its main goal is to help Haitians access knowledge and information through AI technology. Zowobo responds to haitian creole with haitian creole and responds to english with english. Most requests will be in Haitian creole. Zowobo se yon asistan WhatsApp ki la pou ede Ayisyen yo jwenn aksè ak teknoloji AI. Li kapab tande mesaj vwa epi reponn yo nan lang kreyòl ayisyen. Zowobo la pou reponn kesyon, bay enfòmasyon, epi ede ak divès kalite pwoblèm. Si gen yon bagay li pa konnen, l ap di sa klè epi sijere moun nan chèche èd lòt kote. Zowobo toujou ap eseye bay repons ki senp, itil, epi ki fasil pou konprann. Li gen yon ti sans imou tou, men prensipal objektif li se ede Ayisyen yo jwenn aksè ak konesans ak enfòmasyon atravè teknoloji AI.",
        # tools=[{"type": "retrieval"}],
        model="gpt-4o-mini",
        # file_ids=[file.id],
    )
    return assistant


# Use context manager to ensure the shelf file is closed properly
def check_if_thread_exists(wa_id):
    with shelve.open("threads_db") as threads_shelf:
        return threads_shelf.get(wa_id, None)


def store_thread(wa_id, thread_id):
    with shelve.open("threads_db", writeback=True) as threads_shelf:
        threads_shelf[wa_id] = thread_id


def run_assistant(thread, name):
    # Retrieve the Assistant
    assistant = client.beta.assistants.retrieve(OPENAI_ASSISTANT_ID)

    # Run the assistant
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant.id,
        # instructions=f"You are having a conversation with {name}",
    )

    # Wait for completion
    # https://platform.openai.com/docs/assistants/how-it-works/runs-and-run-steps#:~:text=under%20failed_at.-,Polling%20for%20updates,-In%20order%20to
    while run.status != "completed":
        # Be nice to the API
        time.sleep(1)
        run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        print(str(run))

    # Retrieve the Messages
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    new_message = messages.data[0].content[0].text.value
    logging.info(f"Generated message: {new_message}")
    return new_message


def generate_response(message_body, wa_id, name):
    # Check if there is already a thread_id for the wa_id
    thread_id = check_if_thread_exists(wa_id)

    # If a thread doesn't exist, create one and store it
    if thread_id is None:
        logging.info(f"Creating new thread for {name} with wa_id {wa_id}")
        thread = client.beta.threads.create()
        store_thread(wa_id, thread.id)
        thread_id = thread.id

    # Otherwise, retrieve the existing thread
    else:
        logging.info(f"Retrieving existing thread for {name} with wa_id {wa_id}")
        thread = client.beta.threads.retrieve(thread_id)

    # Add message to thread
    message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=message_body,
    )

    # Run the assistant and get the new message
    new_message = run_assistant(thread, name)

    return new_message
