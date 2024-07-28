import os
import logging
import subprocess
from flask import current_app, jsonify
import json
import requests
import whisper
import re
from app.services.openai_service import generate_response

model = whisper.load_model("base")  # Load the Whisper model

def log_http_response(response):
    logging.info(f"Status: {response.status_code}")
    logging.info(f"Content-type: {response.headers.get('content-type')}")
    logging.info(f"Body: {response.text}")

def get_text_message_input(recipient, text):
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
    )

def send_message(data):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
    }

    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"

    try:
        response = requests.post(
            url, data=data, headers=headers, timeout=10
        )  # 10 seconds timeout as an example
        response.raise_for_status()  # Raises an HTTPError if the HTTP request returned an unsuccessful status code
    except requests.Timeout:
        logging.error("Timeout occurred while sending message")
        return jsonify({"status": "error", "message": "Request timed out"}), 408
    except (
        requests.RequestException
    ) as e:  # This will catch any general request exception
        logging.error(f"Request failed due to: {e}")
        return jsonify({"status": "error", "message": "Failed to send message"}), 500
    else:
        # Process the response as normal
        log_http_response(response)
        return response

def process_text_for_whatsapp(text):
    # Remove brackets
    pattern = r"\【.*?\】"
    # Substitute the pattern with an empty string
    text = re.sub(pattern, "", text).strip()

    # Pattern to find double asterisks including the word(s) in between
    pattern = r"\*\*(.*?)\*\*"

    # Replacement pattern with single asterisks
    replacement = r"*\1*"

    # Substitute occurrences of the pattern with the replacement
    whatsapp_style_text = re.sub(pattern, replacement, text)

    return whatsapp_style_text

def process_whatsapp_message(body):
    wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
    name = body["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]

    message = body["entry"][0]["changes"][0]["value"]["messages"][0]
    message_body = message["text"]["body"]

    # OpenAI Integration
    response = generate_response(message_body, wa_id, name)
    response = process_text_for_whatsapp(response)

    # Use the sender's wa_id as the recipient
    data = get_text_message_input(wa_id, response)
    send_message(data)

def process_whatsapp_audio_message(body):
    logging.info(f"Incoming payload: {body}")

    try:
        wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
        name = body["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]

        message = body["entry"][0]["changes"][0]["value"]["messages"][0]

        logging.info(f"Message object: {message}")

        if "voice" in message:
            audio_info = message["voice"]
            audio_file_path = audio_info.get("file")

            logging.info(f"Audio information: {audio_info}")

            if not audio_file_path:
                logging.error("File path not found in the voice message")
                return jsonify({"status": "error", "message": "File path not found in the voice message"}), 400

            # Assuming the file path provided is internal and needs to be accessed differently
            audio_path = download_audio_file_internal(audio_file_path)
            if not audio_path:
                logging.error("Failed to download audio file from internal path")
                return jsonify({"status": "error", "message": "Failed to download audio file from internal path"}), 400

        elif "audio" in message:
            audio_info = message["audio"]
            audio_id = audio_info.get("id")
            if not audio_id:
                logging.error("ID key not found in the audio message")
                return jsonify({"status": "error", "message": "ID key not found in the audio message"}), 400

            # Get the audio URL using the ID
            audio_url, mime_type = get_audio_url(audio_id)
            if not audio_url:
                logging.error("Failed to retrieve audio URL")
                return jsonify({"status": "error", "message": "Failed to retrieve audio URL"}), 400

            logging.info(f"Retrieved audio URL: {audio_url}")

            # Download the audio file
            audio_path = download_audio_file(audio_url, mime_type)
            if not audio_path:
                logging.error("Failed to download audio file")
                return jsonify({"status": "error", "message": "Failed to download audio file"}), 400

        else:
            logging.error("Audio key not found in the message")
            return jsonify({"status": "error", "message": "Audio key not found in the message"}), 400

        # Convert the audio file to WAV format
        wav_path = convert_to_wav(audio_path)
        if not wav_path:
            logging.error("Failed to convert audio file to WAV format")
            return jsonify({"status": "error", "message": "Failed to convert audio file to WAV format"}), 400

        # Transcribe the audio file using Whisper
        transcription = transcribe_audio_file(wav_path)

        # Generate a response using GPT-4
        response = generate_response(transcription, wa_id, name)
        response = process_text_for_whatsapp(response)

        # Send the response back to the sender
        data = get_text_message_input(wa_id, response)
        send_message(data)

        # Clean up audio files
        os.remove(audio_path)
        os.remove(wav_path)

    except Exception as e:
        logging.error(f"Error processing audio message: {e}")
        return jsonify({"status": "error", "message": "Failed to process audio message"}), 500

def download_audio_file_internal(file_path):
    # This function assumes file_path is an internal path and needs to be handled accordingly
    logging.info(f"Attempting to access internal audio file from path: {file_path}")
    # Implement logic to access the internal file path here, if applicable
    # This is a placeholder implementation
    try:
        with open(file_path, 'rb') as f:
            audio_path = "audio_internal.ogg"
            with open(audio_path, 'wb') as audio_file:
                audio_file.write(f.read())
        return os.path.abspath(audio_path)
    except Exception as e:
        logging.error(f"Failed to access internal audio file: {e}")
        return None

def get_audio_url(media_id):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
    }
    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{media_id}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        media_data = response.json()
        logging.info(f"Media data: {media_data}")
        return media_data.get("url"), media_data.get("mime_type")
    else:
        logging.error(f"Failed to retrieve media URL: {response.status_code} {response.text}")
        return None, None

def download_audio_file(url, mime_type):
    headers = {
        "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36",
    }
    logging.info(f"Attempting to download audio file from URL: {url}")
    
    try:
        response = requests.get(url, headers=headers, stream=True)
        logging.info(f"Response headers: {response.headers}")
        logging.info(f"Response status code: {response.status_code}")

        # Log the first 200 bytes of the content to check if it starts as expected
        content_preview = response.content[:200]
        logging.info(f"Content preview: {content_preview}")

    except requests.RequestException as e:
        logging.error(f"Request to download audio failed: {e}")
        return None

    if response.status_code == 200:
        extension = 'ogg' if 'ogg' in mime_type else 'mp3'
        audio_path = os.path.abspath(f"audio.{extension}")
        try:
            with open(audio_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logging.info(f"Audio file downloaded successfully: {audio_path}")
            return audio_path
        except Exception as e:
            logging.error(f"Failed to write audio file: {e}")
            return None
    else:
        logging.error(f"Failed to download audio file: {response.status_code} {response.text}")
        return None

def convert_to_wav(input_path):
    output_path = os.path.splitext(input_path)[0] + ".wav"
    try:
        result = subprocess.run(
            ["ffmpeg", "-i", input_path, output_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        logging.info(f"Converted audio file to WAV format: {output_path}")
        logging.info(f"FFmpeg stdout: {result.stdout.decode()}")
        logging.info(f"FFmpeg stderr: {result.stderr.decode()}")
        return output_path
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to convert audio file to WAV: {e.stderr.decode()}")
        return None

def transcribe_audio_file(audio_path):
    logging.info(f"Starting transcription for file: {audio_path}")
    result = model.transcribe(audio_path)
    return result['text']

def is_valid_whatsapp_message(body):
    """
    Check if the incoming webhook event has a valid WhatsApp message structure.
    """
    return (
        body.get("object")
        and body.get("entry")
        and body["entry"][0].get("changes")
        and body["entry"][0]["changes"][0].get("value")
        and body["entry"][0]["changes"][0]["value"].get("messages")
        and body["entry"][0]["changes"][0]["value"]["messages"][0]
    )
