from datetime import datetime
from fastapi import FastAPI, Header, HTTPException, Query
import gradio as gr
import os
from pathlib import Path
import re
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
    text = re.sub(r'\s+', ' ', text)
    return text

@app.get("/submit")
def submit_get(
    text: str = Query(..., min_length=1),
    user: str = Query(..., min_length=1),
):
    global items, max_items

    text = scrub_input(text)
    print(f"Request: {user}: {text}")
    with lock:
        if len(items) < max_items:
            items.append([user, text, datetime.now().strftime("%H:%M:%S")])
            ok_status = True
            status = f"Place in queue: {len(items)}"
        else:
            ok_status = False
            status = "Queue full"

        return {"ok": ok_status, "status": status}

def update_queue():
    global items, played_list
    queue_md = ""
    if items:
        for item in items:
            queue_md += f"* [{item[2]}] **{item[0]}:** {item[1]}\n"
    played_md = ""
    if played_list:
        for item in reversed(played_list):
            played_md += f"* [{item[2]}] **{item[0]}:** {item[1]}\n"

    return [
        gr.update(value=queue_md),
        gr.update(value=played_md),
    ]

def get_items(user, text, trigger):
    global items
    now = None
    with lock:
        top_item = None
        if text == "" and len(items):
            top_item = items.pop(0)
            now=datetime.now().strftime("%H:%M:%S")

        return [
            gr.update() if top_item is None else gr.update(value=top_item[0]), # User
            gr.update() if top_item is None else gr.update(value=top_item[1]), # Text
            gr.update() if now is None else gr.update(value=now),
        ]

def clone_voice(user, text):
    global played_list
    text = scrub_input(text)
    snd = tts.clone_voice(text)
    output = Path(os.getcwd()) / 'output'
    path = str(output / snd)
    with lock:
        now = datetime.now().strftime("%H:%M:%S")
        played_list.append([user, text, now, snd])
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
                        admin_name = gr.Textbox(
                            label = "Webui user-name",
                            value = "Admin",
                        )
                        max_length = gr.Slider(
                            label = "Max message length (characters)",
                            value = tts.get_max_len(),
                            minimum = 1,
                            maximum = 500,
                        )
                        max_length.change(fn=tts.set_max_len, inputs=max_length)
                        max_tokens = gr.Slider(
                            label = "Max tokens (~10 tokens per second of audio)",
                            value = tts.get_max_tokens(),
                            minimum = 1,
                            maximum = 1500,
                        )
                        max_tokens.change(fn=tts.set_max_tokens, inputs=max_tokens)


                gr.Markdown("### Please keep this tab open to keep JavaScript happy.")
            gr.Markdown("https://github.com/yownas/text-to-slop")

        with gr.Column():
            gr.Markdown("## Request queue:")
            table = gr.Markdown()
            gr.Markdown("## Played:")
            played = gr.Markdown()

            queue_timer = gr.Timer(2)
            timer = gr.Timer(2)
            queue_name = gr.State("")
            queue_text = gr.State("")

    queue_timer.tick(
        fn=update_queue,
        outputs=[table, played],
    )
    timer.tick(
        fn=get_items,
        inputs=[queue_name, queue_text, hidden_trigger],
        outputs=[queue_name, queue_text, hidden_trigger]
    )
    # fill on page load
    webui.load(
        fn=get_items,
        inputs=[queue_name, queue_text, hidden_trigger],
        outputs=[queue_name, queue_text, hidden_trigger]
    )
    input_text.submit(
        fn=clone_voice,
        inputs=[admin_name, input_text],
        outputs=[slop_voice, input_text]
    )
    hidden_trigger.change(
        fn=clone_voice,
        inputs=[queue_name, queue_text],
        outputs=[slop_voice, queue_text]
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

