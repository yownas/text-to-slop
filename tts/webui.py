from datetime import datetime
from fastapi import FastAPI, Header, HTTPException, Query
import gradio as gr
import os
from pathlib import Path
import threading
import time
from tts.qwen3tts import TTS
import uvicorn

import warnings
warnings.filterwarnings("ignore", message=".*HTTP_422_UNPROCESSABLE_ENTITY.*")

reference_voices = []
def update_reference_voices():
    global reference_voices
    files = []
    folder = Path(os.getcwd()) / "reference"
    for ext in ("mp3", "wav", "flac", "ogg"):
        files += Path(folder).glob(f"*.{ext}")
    reference_voices = sorted([Path(p).name for p in files])
tts = TTS()
update_reference_voices()
tts.load_reference(reference_voices[0])
items = []                 # shared state
max_items = 10

# HTTP api...
lock = threading.Lock()
app = FastAPI()

@app.get("/submit")
def submit_get(
    text: str = Query(..., min_length=1),
):
    global items, max_items

    if len(items) < max_items:
        with lock:
            items.append([datetime.now().strftime("%H:%M:%S"), text])
            items = list(sorted(items))
            ok_status = True
            status = f"Place in queue: {len(items)}"
    else:
        ok_status = False
        status = "Queue full"

    return {"ok": ok_status, "status": status}

def get_items(text, trigger):
    global items
    with lock:
        top_item = ""
        if text == "" and len(items):
            top_item = items.pop()[1]
            trigger=datetime.now().strftime("%H:%M:%S")

        return [
            gr.update(value=items),
            gr.update() if top_item == "" else gr.update(value=top_item),
            gr.update(value=trigger),
        ]

def scrub_input(text):
    text = text.strip()
    return text

def clone_voice(text):
    text = scrub_input(text)
    snd = tts.clone_voice(text)
    return [
        gr.update(label=text, value=snd),
        gr.update(),
        gr.update(value="")
    ]

def select_voice(voice):
    tts.load_reference(voice)

def select_language(lang):
    tts.set_language(lang)

# Webui...
with gr.Blocks() as webui:
    with gr.Row():
        with gr.Column():
            with gr.Group():
                slop_voice = gr.Audio(
                    show_label = True,
                    label = "<>",
                    autoplay = True,
                )
                input_text = gr.Textbox(
                    show_label = False,
                    submit_btn = "Talk",
                    placeholder = "Enter text here...",
                )
                hidden_trigger = gr.Textbox(
                    visible = 'hidden',
                )

            with gr.Group():
                with gr.Row():
                    reference_file = gr.Dropdown(
                        label = "Reference voice",
                        choices = reference_voices,
                        value = reference_voices[0],
                        scale = 4,
                    )
                    language = gr.Dropdown(
                        label = "Language",
                        show_label = True,
                        interactive = True,
                        choices = [
                            'Chinese',
                            'English',
                            'French',
                            'German',
                            'Italian',
                            'Japanese',
                            'Korean',
                            'Portuguese',
                            'Russian',
                            'Spanish',
                        ],
                        value=tts.get_language(),
                        scale = 1,
                    )
                with gr.Row():
                    max_length = gr.Slider(
                        label = "Max message length",
                        value = tts.get_max_len(),
                        minimum = 1,
                        maximum = 500,
                        scale = 3,
                    )
                    max_length.change(fn=tts.set_max_len, inputs=max_length)

                gr.Markdown("### Please keep this tab open.")

        with gr.Column():
            gr.Markdown("### Incoming submissions at http://127.0.0.1:7860/submit?text=a+short+example+text")
            table = gr.Dataframe(
                headers = ["Time", "Text"],
                interactive = False,
                buttons = [],
            )
            timer = gr.Timer(2)
            played = gr.Dataframe(
                headers = ['Text', '▶'],
                buttons = [],
            )

    timer.tick(get_items, inputs=[input_text, hidden_trigger], outputs=[table, input_text, hidden_trigger])
    webui.load(get_items, inputs=[input_text, hidden_trigger], outputs=[table, input_text, hidden_trigger]) # fill on page load
    input_text.submit(fn=clone_voice, inputs=input_text, outputs=[slop_voice, played, input_text])
    hidden_trigger.change(fn=clone_voice, inputs=input_text, outputs=[slop_voice, played, input_text])
    reference_file.select(fn=select_voice, inputs=reference_file)
    language.select(fn=select_language, inputs=language)

# Mount Gradio onto the FastAPI app AFTER the routes are defined.
# allowed_paths moves here from launch().
app = gr.mount_gradio_app(app, webui, path="/", allowed_paths=["."])

def launch_me():
    uvicorn.run(app, host="0.0.0.0", port=7860, access_log=False)

if __name__ == "__main__":
    launch_me()

