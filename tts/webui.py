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
played_list = []

# HTTP api...
lock = threading.Lock()
app = FastAPI()

def scrub_input(text):
    text = text.strip()
    return text

@app.get("/submit")
def submit_get(
    text: str = Query(..., min_length=1),
):
    global items, max_items

    text = scrub_input(text)
    print(f"Request: {text}")
    with lock:
        if len(items) < max_items:
            items.append([text, datetime.now().strftime("%H:%M:%S")])
            ok_status = True
            status = f"Place in queue: {len(items)}"
        else:
            ok_status = False
            status = "Queue full"

        return {"ok": ok_status, "status": status}

def get_items(text, trigger):
    global items, played_list
    now = None
    with lock:
        top_item = ""
        if text == "" and len(items):
            top_item = items.pop(0)[0]
            now=datetime.now().strftime("%H:%M:%S")

        return [
            gr.update(value=items),
            gr.update(value=played_list, label=now),
            gr.update() if top_item == "" else gr.update(value=top_item),
            gr.update() if now is None else gr.update(value=now),
        ]

def clone_voice(text):
    global played_list
    text = scrub_input(text)
    snd = tts.clone_voice(text)
    output = Path(os.getcwd()) / 'output'
    path = str(output / snd)
    with lock:
        played_list.append([text, snd])
        return [
            gr.update(label=text, value=path),
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
                    with gr.Accordion(
                            label = "AI settings",
                            open = False
                        ):
                        max_length = gr.Slider(
                            label = "Max message length",
                            value = tts.get_max_len(),
                            minimum = 1,
                            maximum = 500,
                        )
                        max_length.change(fn=tts.set_max_len, inputs=max_length)
                        max_tokens = gr.Slider(
                            label = "Max tokens",
                            value = tts.get_max_tokens(),
                            minimum = 1,
                            maximum = 3000,
                        )
                        max_tokens.change(fn=tts.set_max_tokens, inputs=max_tokens)


                gr.Markdown("### Please keep this tab open.")

        with gr.Column():
            gr.Markdown("### Incoming submissions at http://127.0.0.1:7860/submit?text=a+short+example+text")
            table = gr.Dataframe(
                headers = ['Text', 'Time'],
                column_widths = ['75%', '25%'],
                row_count = (1, "dynamic"),
                interactive = False,
                buttons = [],
            )
            played = gr.Dataframe(
                label = "Played",
                show_label = True,
                headers = ['Text', 'File'],
                column_widths = ['75%', '25%'],
                row_count = (1, "dynamic"),
                interactive = False,
                buttons = [],
            )
            timer = gr.Timer(2)

    timer.tick(
        fn=get_items,
        inputs=[input_text, hidden_trigger],
        outputs=[table, played, input_text, hidden_trigger]
    )
    # fill on page load
    webui.load(
        fn=get_items,
        inputs=[input_text, hidden_trigger],
        outputs=[table, played, input_text, hidden_trigger]
    )
    input_text.submit(
        fn=clone_voice,
        inputs=input_text,
        outputs=[slop_voice, input_text]
    )
    hidden_trigger.change(
        fn=clone_voice,
        inputs=input_text,
        outputs=[slop_voice, input_text]
    )
    reference_file.select(
        fn=select_voice,
        inputs=reference_file
    )
    language.select(
        fn=select_language,
        inputs=language
    )
    # Stop/start timer when audio is playing
    slop_voice.play(lambda: gr.Timer(active=False), outputs=timer)
    for ev in (slop_voice.pause, slop_voice.stop, slop_voice.clear): 
        ev(lambda: gr.Timer(active=True), outputs=timer)

# Mount Gradio onto the FastAPI app AFTER the routes are defined.
# allowed_paths moves here from launch().
app = gr.mount_gradio_app(app, webui, path="/", allowed_paths=["."])

def launch_me():
    uvicorn.run(app, host="0.0.0.0", port=7860, access_log=False)

if __name__ == "__main__":
    launch_me()

