'''
webui for text-to-slop - a silly locally run text-to-speech
'''

from tts.qwen3tts import TTS
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
import gradio as gr
from datetime import datetime
import html
import os
from pathlib import Path
import re
import threading
import uvicorn
import warnings
warnings.filterwarnings("ignore", message=".*HTTP_422_UNPROCESSABLE_ENTITY.*")

reference_voices = []
def update_reference_voices():
    '''
    Check for audio files to use as refrence voices
    '''
    global reference_voices
    files = []
    folder = Path(os.getcwd()) / "reference"
    for ext in ("mp3", "wav", "flac", "ogg"):
        files += Path(folder).glob(f"*.{ext}")
    reference_voices = sorted([Path(p).name for p in files])
    return gr.update(choices=reference_voices)

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
    '''
    Some simple cleanup of the text string
    '''
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    return text

@app.get("/submit")
def submit_get(
    text: str = Query(..., min_length=1),
    user: str = Query(..., min_length=1),
):
    """ Handle submissions via fastapi """
    global items, max_items

    text = scrub_input(text)
    with lock:
        if len(items) < max_items:
            items.append([user, text, datetime.now().strftime("%H:%M:%S")])
            ok_status = True
            status = f"Place in queue: {len(items)}"
        else:
            ok_status = False
            status = "Queue full"

        return {"ok": ok_status, "status": status}

@app.get("/sound")
def sound_get(
    text: str = Query(..., min_length=1),
    user: str = Query(..., min_length=1),
):
    """ Get sound file directly via fastapi """
    global played_list

    text = scrub_input(text)
    path = clone_voice(user, text, return_file=True)

    return FileResponse(
        path=str(path),
        media_type="audio/mpeg",
    )

def update_queue():
    """ Update webui """
    global items, played_list
    queue_md = ""
    if items:
        for item in items:
            queue_md += "* [{time}] **{name}:** {text}\n".format(
                name = html.escape(item[0]),
                text = html.escape(item[1]),
                time = html.escape(item[2]),
            )
    played_md = ""
    if played_list:
        for item in reversed(played_list):
            played_md += "* [{time}] **{name}:** {text}\n".format(
                name = html.escape(item[0]),
                text = html.escape(item[1]),
                time = html.escape(item[2]),
            )

    return [
        gr.update(value=queue_md),
        gr.update(value=played_md),
    ]

def get_items(text):
    """ Update webui with data """
    global items
    now = None
    with lock:
        top_item = None
        if text == "" and len(items) > 0:
            top_item = items.pop(0)
            now=datetime.now().strftime("%H:%M:%S")

        return [
            gr.update() if top_item is None else gr.update(value=top_item[0]), # User
            gr.update() if top_item is None else gr.update(value=top_item[1]), # Text
            gr.update() if now is None else gr.update(value=now),
        ]

def clone_voice(user, text, return_file=False):
    """ Generate sound clip """
    global played_list
    text = scrub_input(text)
    if len(text) <= 0:
        return [
            gr.update(),
            gr.update()
        ]
    path = tts.clone_voice(text, user=user)
    with lock:
        now = datetime.now().strftime("%H:%M:%S")
        played_list.append([user, ("**BLOCKED** " if path is None else "") + text, now, path])
        if return_file:
            return(path)
        else:
            if path is None:
                gr.Warning(f"{user} sent a message that was blocked!")
                return [
                    gr.update(),
                    gr.update(value="")
                ]
            else:
                return [
                    gr.update(label=text, value=path),
                    gr.update(value="")
                ]

def select_voice(voice): tts.load_reference(voice)
def select_language(lang): tts.set_language(lang)

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
                    voice_reload = gr.Button(value="Reload")
                    reference_file = gr.Dropdown(
                        label = "Reference voice",
                        choices = reference_voices,
                        value = reference_voices[0],
                        scale = 4,
                        buttons = [voice_reload],
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
                            maximum = 1000,
                        )
                        max_length.change(fn=tts.set_max_len, inputs=max_length)
                        max_tokens = gr.Slider(
                            label = "Max tokens (~10 tokens per second of audio)",
                            value = tts.get_max_tokens(),
                            minimum = 1,
                            maximum = 2000,
                        )
                        max_tokens.change(fn=tts.set_max_tokens, inputs=max_tokens)

                        tts_temperature = gr.Slider(
                            label = "Temperature: Expressiveness (robotic -> natural)",
                            value = tts.get_tts_temperature(),
                            minimum = 0.01,
                            maximum = 2.0,
                            step = 0.01
                        )
                        tts_temperature.change(fn=tts.set_tts_temperature, inputs=tts_temperature)

                        tts_top_k = gr.Slider(
                            label = "top_k: Variety",
                            value = tts.get_tts_top_k(),
                            minimum = 1,
                            maximum = 3072,
                            step = 1
                        )
                        tts_top_k.change(fn=tts.set_tts_top_k, inputs=tts_top_k)

                        tts_top_p = gr.Slider(
                            label = "top_p: Precision",
                            value = tts.get_tts_top_p(),
                            minimum = 0.0,
                            maximum = 1.0,
                            step = 0.01
                        )
                        tts_top_p.change(fn=tts.set_tts_top_p, inputs=tts_top_p)
                with gr.Row():
                    with gr.Accordion(
                            label = "Moderation",
                            open = False
                        ):
                        with gr.Row():
                            tts_mod_enabled = gr.Checkbox(label = "Enabled", value = tts.mod_enabled)
                            tts_mod_enabled.change(fn=tts.set_mod_enabled, inputs=tts_mod_enabled)
                            tts_mod_verbose = gr.Checkbox(label = "Verbose", value = tts.mod_verbose)
                            tts_mod_verbose.change(fn=tts.set_mod_verbose, inputs=tts_mod_verbose)

                        def update_tts_mod_value(value, evt: gr.EventData):
                            label = tts.mod_meaning_labels.get(evt.target.label, None)
                            if label is not None:
                                tts.mod_labels[label] = value
                        with gr.Group():
                            mod_slider = {}
                            for label in ['H', 'SH', 'V', 'S', 'HR', 'V2', 'S3', 'H2']:
                                mod_slider[label] = gr.Slider(
                                    label=tts.mod_label_meanings[label],
                                    value=tts.mod_labels[label],
                                    minimum=-1.0 if tts.mod_allow_negative else 0.0,
                                    maximum=1.0,
                                    step=0.01,
                                )
                                mod_slider[label].change(fn=update_tts_mod_value, inputs=mod_slider[label])

                gr.Markdown("### Please keep this tab open to keep JavaScript happy.")
            gr.Markdown("https://github.com/yownas/text-to-slop")

        with gr.Column():
            gr.Markdown("## Request queue:")
            table = gr.Markdown(sanitize_html=True)
            gr.Markdown("## Played:")
            played = gr.Markdown(sanitize_html=True)

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
        inputs=[queue_text],
        outputs=[queue_name, queue_text, hidden_trigger]
    )
    # fill on page load
    webui.load(
        fn=get_items,
        inputs=[queue_text],
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
    voice_reload.click(
        fn=update_reference_voices,
        outputs=[reference_file],
    )

# Mount Gradio onto the FastAPI app AFTER the routes are defined.
# allowed_paths moves here from launch().
app = gr.mount_gradio_app(app, webui, path="/", allowed_paths=["."])

def launch_me():
    """ Run TTS, run! """
    uvicorn.run(app, host="0.0.0.0", port=7860, access_log=False, timeout_graceful_shutdown=2)

if __name__ == "__main__":
    launch_me()
