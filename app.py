from flask import Flask, render_template, jsonify, request
from ollama import chat

import sounddevice as sd
import numpy as np
import speech_recognition as sr

from scipy.io.wavfile import write

import subprocess
import time
import threading


app = Flask(__name__)


# =========================================================
# LUMI MEMORY
# =========================================================

messages = [
    {
        "role": "system",
        "content": (
            "You are LUMI, a helpful AI voice assistant. "
            "Keep answers friendly, natural, calm, and conversational."
        )
    }
]


# =========================================================
# SPEECH PROCESS
# =========================================================

speech_process = None

speech_lock = threading.Lock()


# =========================================================
# ASSISTANT STATE
# =========================================================

assistant_state = "ready"

state_lock = threading.Lock()


def set_state(state):

    global assistant_state

    with state_lock:
        assistant_state = state

    print("STATE:", state)


def get_state():

    with state_lock:
        return assistant_state


# =========================================================
# MICROPHONE LEVEL
# =========================================================
# 0.0 = silence
# 1.0 = loud voice
#
# This value is sent to the browser while the user speaks.
# The browser uses it to control the orb.
# =========================================================

mic_level = 0.0

mic_level_lock = threading.Lock()


def set_mic_level(level):

    global mic_level

    with mic_level_lock:

        mic_level = max(
            0.0,
            min(1.0, float(level))
        )


def get_mic_level():

    with mic_level_lock:

        return mic_level


# =========================================================
# TEXT TO SPEECH
# =========================================================

def speak(text):

    global speech_process

    powershell_command = r"""
Add-Type -AssemblyName System.Speech

$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer

$speaker.SelectVoice("Microsoft Zira Desktop")

$speaker.Rate = -1
$speaker.Volume = 100

$speaker.Speak([Console]::In.ReadToEnd())
"""


    process = subprocess.Popen(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            powershell_command
        ],
        stdin=subprocess.PIPE,
        text=True
    )


    with speech_lock:

        speech_process = process


    set_state("speaking")


    try:

        process.communicate(
            input=text
        )

    except Exception:

        pass

    finally:

        with speech_lock:

            if speech_process == process:

                speech_process = None

        set_state("ready")


# =========================================================
# STOP LUMI SPEAKING
# =========================================================

def stop_speaking():

    global speech_process

    with speech_lock:

        if speech_process is not None:

            try:

                speech_process.terminate()

            except Exception:

                pass

            speech_process = None


    set_mic_level(0)

    set_state("ready")

    print("Speech stopped.")


# =========================================================
# RECORD USER VOICE
# =========================================================

def record_voice():

    SAMPLE_RATE = 16000

    BLOCK_SIZE = 1024

    SILENCE_SECONDS = 1.5

    MAX_RECORDING_SECONDS = 30

    THRESHOLD = 500


    audio_chunks = []

    started_speaking = False

    silence_start = None

    start_time = time.time()


    set_state("listening")

    set_mic_level(0)


    print("\nListening...")


    # -----------------------------------------------------
    # MICROPHONE CALLBACK
    # -----------------------------------------------------

    def callback(
        indata,
        frames,
        time_info,
        status
    ):

        if status:

            print(status)


        # Save microphone audio

        audio_chunks.append(
            indata.copy()
        )


        # -------------------------------------------------
        # CALCULATE MICROPHONE VOLUME
        # -------------------------------------------------

        audio = indata.astype(
            np.float32
        )


        volume = np.sqrt(
            np.mean(
                audio ** 2
            )
        )


        # -------------------------------------------------
        # CONVERT VOLUME TO 0-1
        # -------------------------------------------------

        normalized = (
            volume - 150
        ) / 2500


        normalized = max(
            0.0,
            min(1.0, normalized)
        )


        # -------------------------------------------------
        # SMOOTH MICROPHONE LEVEL
        # -------------------------------------------------

        old_level = get_mic_level()


        smooth_level = (
            old_level * 0.65
            +
            normalized * 0.35
        )


        set_mic_level(
            smooth_level
        )


    # -----------------------------------------------------
    # OPEN MICROPHONE
    # -----------------------------------------------------

    with sd.InputStream(

        samplerate=SAMPLE_RATE,

        channels=1,

        dtype="int16",

        blocksize=BLOCK_SIZE,

        callback=callback

    ):


        while True:

            time.sleep(0.05)


            if not audio_chunks:

                continue


            current_audio = (
                audio_chunks[-1]
            )


            volume = np.sqrt(
                np.mean(
                    current_audio.astype(
                        np.float32
                    ) ** 2
                )
            )


            # -------------------------------------------------
            # SPEECH DETECTED
            # -------------------------------------------------

            if volume > THRESHOLD:

                if not started_speaking:

                    print(
                        "Speech detected!"
                    )


                started_speaking = True

                silence_start = None


            # -------------------------------------------------
            # SILENCE AFTER SPEECH
            # -------------------------------------------------

            elif started_speaking:

                if silence_start is None:

                    silence_start = time.time()


                elif (
                    time.time()
                    -
                    silence_start
                    >= SILENCE_SECONDS
                ):

                    print(
                        "Silence detected."
                    )

                    break


            # -------------------------------------------------
            # MAXIMUM RECORDING TIME
            # -------------------------------------------------

            if (
                time.time()
                -
                start_time
                >= MAX_RECORDING_SECONDS
            ):

                print(
                    "Maximum recording time reached."
                )

                break


    # -----------------------------------------------------
    # STOP MICROPHONE LEVEL
    # -----------------------------------------------------

    set_mic_level(0)


    if not audio_chunks:

        set_state("ready")

        return None


    # -----------------------------------------------------
    # COMBINE AUDIO
    # -----------------------------------------------------

    audio = np.concatenate(
        audio_chunks
    )


    # -----------------------------------------------------
    # SAVE WAV FILE
    # -----------------------------------------------------

    write(
        "test_recording.wav",
        SAMPLE_RATE,
        audio
    )


    print(
        "Recording finished!"
    )


    return "test_recording.wav"


# =========================================================
# SPEECH TO TEXT
# =========================================================

def speech_to_text(filename):

    recognizer = sr.Recognizer()


    try:

        with sr.AudioFile(filename) as source:

            print(
                "Understanding what you said..."
            )


            recorded_audio = recognizer.record(
                source
            )


        text = recognizer.recognize_google(
            recorded_audio
        )


        print(
            "You said:",
            text
        )


        return text


    except sr.UnknownValueError:

        print(
            "Sorry, I couldn't understand you."
        )

        return None


    except sr.RequestError as e:

        print(
            "Speech recognition error:",
            e
        )

        return None


# =========================================================
# RESPONSE LENGTH
# =========================================================

def get_response_instruction(length):

    if length == "short":

        return (
            "Give a very short answer. "
            "Use only 1 or 2 sentences. "
            "Do not add unnecessary details."
        )


    elif length == "detailed":

        return (
            "Give a detailed answer. "
            "Explain the topic clearly and "
            "include useful examples when appropriate."
        )


    else:

        return (
            "Give a normal-length answer. "
            "Be clear and concise without "
            "unnecessary details."
        )


# =========================================================
# RUN ASSISTANT
# =========================================================

def run_assistant(response_length):

    # -----------------------------------------------------
    # RECORD USER
    # -----------------------------------------------------

    filename = record_voice()


    if filename is None:

        set_state("ready")

        return {
            "user_text": "",
            "response": "I didn't hear anything."
        }


    # -----------------------------------------------------
    # CONVERT SPEECH TO TEXT
    # -----------------------------------------------------

    text = speech_to_text(
        filename
    )


    if not text:

        set_state("ready")

        return {
            "user_text": "",
            "response":
                "Sorry, I couldn't understand you."
        }


    # -----------------------------------------------------
    # EXIT COMMAND
    # -----------------------------------------------------

    if text.lower().strip() in [
        "exit",
        "quit",
        "goodbye"
    ]:

        answer = "Goodbye!"


        threading.Thread(
            target=speak,
            args=(answer,),
            daemon=True
        ).start()


        return {
            "user_text": text,
            "response": answer
        }


    # -----------------------------------------------------
    # SAVE USER MESSAGE
    # -----------------------------------------------------

    messages.append(
        {
            "role": "user",
            "content": text
        }
    )


    # -----------------------------------------------------
    # RESPONSE INSTRUCTION
    # -----------------------------------------------------

    instruction = get_response_instruction(
        response_length
    )


    messages_for_ai = messages + [

        {
            "role": "system",
            "content": instruction
        }

    ]


    # -----------------------------------------------------
    # THINKING
    # -----------------------------------------------------

    set_state("thinking")

    set_mic_level(0)


    print(
        "\nLUMI is thinking..."
    )


    # -----------------------------------------------------
    # ASK OLLAMA
    # -----------------------------------------------------

    try:

        response = chat(

            model="llama3.2:3b",

            messages=messages_for_ai

        )


        answer = response.message.content


    except Exception as e:

        print(
            "Ollama error:",
            e
        )


        answer = (
            "Sorry, I couldn't connect "
            "to my local AI model."
        )


        set_state("ready")


        return {
            "user_text": text,
            "response": answer
        }


    # -----------------------------------------------------
    # SAVE LUMI RESPONSE
    # -----------------------------------------------------

    messages.append(
        {
            "role": "assistant",
            "content": answer
        }
    )


    print(
        "\nLUMI:",
        answer
    )


    # -----------------------------------------------------
    # SPEAK
    # -----------------------------------------------------

    print(
        "\nLUMI is speaking..."
    )


    threading.Thread(
        target=speak,
        args=(answer,),
        daemon=True
    ).start()


    return {
        "user_text": text,
        "response": answer
    }


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================================================
# ASK
# =========================================================

@app.route(
    "/ask",
    methods=["POST"]
)
def ask():

    data = request.get_json()


    response_length = data.get(
        "response_length",
        "normal"
    )


    result = run_assistant(
        response_length
    )


    return jsonify(
        result
    )


# =========================================================
# STOP
# =========================================================

@app.route(
    "/stop",
    methods=["POST"]
)
def stop():

    stop_speaking()


    return jsonify(
        {
            "status": "stopped"
        }
    )


# =========================================================
# ASSISTANT STATUS
# =========================================================

@app.route(
    "/assistant_status"
)
def assistant_status():

    return jsonify(
        {
            "state": get_state(),

            "mic_level":
                get_mic_level()
        }
    )


# =========================================================
# START FLASK
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=False,
        threaded=True
    )