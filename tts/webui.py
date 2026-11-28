'''
webui for text-to-slop - a silly locally run text-to-speech
'''

from tts.qwen3tts import TTS
from tts.mod import MOD
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
import gradio as gr
from datetime import datetime
import html
import os
import time
from pathlib import Path
import re
import threading
import uvicorn
import warnings
warnings.filterwarnings("ignore", message=".*HTTP_422_UNPROCESSABLE_ENTITY.*")
import __main__

reference_voices = []
def update_reference_voices():
    '''
    Check for audio files to use as refrence voices
    '''
    global reference_voices
    files = []
    folder = Path(__main__.__file__).resolve().parent  / 'reference'
    for ext in ("mp3", "wav", "flac", "ogg"):
        files += Path(folder).glob(f"*.{ext}")
    reference_voices = sorted([Path(p).name for p in files])
    return gr.update(choices=reference_voices)

tts = TTS()
mod = MOD()
update_reference_voices()
tts.load_reference(reference_voices[0])

ID = 0
max_queue = 10
inbox_list = [] # [ID, user, text, datetime.now().strftime("%H:%M:%S"), isok]

queue_list = []                 # shared state
played_list = []

# HTTP api...
lock = threading.Lock()
app = FastAPI()

# Moderator thread
def mod_worker():
    """
    Check inbox and move text to TTS queue if they are appropriate
    """
    global mod, lock, inbox_list, queue_list

    print(f"Slop moderator started...")
    while True:
        with lock:
            if len(inbox_list) > 0:
                post = inbox_list.pop(0)
                post[4] = mod.moderate_text(post[2], user=post[1])
                queue_list.append(post)
        time.sleep(0.3)
threading.Thread(target=mod_worker, daemon=True).start()

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
    global ID, inbox_list, max_queue

    text = scrub_input(text)
    with lock:
        if len(queue_list) < max_queue:
            ID += 1
            inbox_list.append([ID, user, text, datetime.now().strftime("%H:%M:%S"), False])
            ok_status = True
            status = f"Place in queue: {len(inbox_list)}"
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
    global ID, queue_list, played_list

    # FIXME add to queue, moderated
    text = scrub_input(text)
    path = clone_voice(user, text, return_file=True)

    return FileResponse(
        path=str(path),
        media_type="audio/mpeg",
    )

def update_queue():
    """ Update webui """
    global queue_list, played_list
    queue_html = "<ul>"
    if queue_list:
        for item in queue_list:
            queue_html += """<li>
            <a href=# onClick=\"js_command('skip {qid}'); return false;\">🚮</a>
            [{time}]
            <a href=# onClick=\"js_command('toggleok {qid}'); return false;\">{isok}</a>
            <b>{user}:</b> {text}\n""".format(
                qid = str(item[0]),
                user = html.escape(item[1]),
                text = html.escape(item[2]),
                time = html.escape(item[3]),
                isok = "👍" if item[4] else "❌",
            )
    queue_html += "</ul>"
    played_html = "<ul>"
    if played_list:
        for item in reversed(played_list):
            played_html += "<li><a href=# onClick=\"js_command('play {file}'); return false;\">[{time}]</a> <b>{user}:</b> {text}\n".format(
                user = html.escape(item[1]),
                text = html.escape(item[2]),
                time = html.escape(item[3]),
                file = html.escape(item[4]),
            )
    played_html += "</ul>"

    return [
        gr.update(value=queue_html),
        gr.update(value=played_html),
    ]

def get_items(enabled, text):
    """ Update webui with data """
    global queue_list
    if not enabled:
        return [gr.update(), gr.update(), gr.update()]
    now = None
    with lock:
        top_item = None
        if text == "" and len(queue_list) > 0:
            for i, item in enumerate(queue_list):
                if item[4]: # isok?
                    top_item = queue_list.pop(i)
                    now=datetime.now().strftime("%H:%M:%S")
                    break

        return [
            gr.update() if top_item is None else gr.update(value=top_item[1]), # User
            gr.update() if top_item is None else gr.update(value=top_item[2]), # Text
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
        played_list.append([0, user, text, now, path])
        if return_file:
            return(path)
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
                        tts_use_cpu = gr.Checkbox(
                            label = "Use CPU (Slower, but will not use GPU VRAM)",
                            value = tts.use_cpu,
                        )
                        tts_use_cpu.change(fn=tts.set_use_cpu, inputs=tts_use_cpu)
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
                            def block_user(username):
                                mod.mod_block_user(username)
                                gr.Info(f"{username} blocked.")
                                return gr.update(value="")
                            with gr.Group():
                                block_user_btn = gr.Button(
                                    value = "Block!")
                                block_user_txt = gr.Textbox(
                                    label = "Block user",
                                    show_label = True,
                                    placeholder = "Username",
                                    buttons=[block_user_btn]
                                )
                            block_user_txt.submit(fn=block_user, inputs=block_user_txt, outputs=block_user_txt)
                            block_user_btn.click(fn=block_user, inputs=block_user_txt, outputs=block_user_txt)
                        with gr.Row():
                            tts_mod_enabled = gr.Checkbox(label = "Automod enabled", value = mod.mod_enabled, scale = 3)
                            tts_mod_enabled.change(fn=mod.set_mod_enabled, inputs=tts_mod_enabled)
                            tts_mod_reload = gr.Button(value = "Reload", scale = 1)
                            tts_mod_reload.click(fn=mod.mod_reload)

                        def update_tts_mod_value(value, evt: gr.EventData):
                            label = mod.mod_meaning_labels.get(evt.target.label, None)
                            if label is not None:
                                mod.mod_labels[label][1] = value
                        with gr.Group():
                            gr.Markdown("Tolerance level:")
                            mod_slider = {}
                            #for label in ['H', 'SH', 'V', 'S', 'HR', 'V2', 'S3', 'H2']:
                            for label in mod.mod_labels.keys():
                                if mod.mod_labels[label][2]:
                                    mod_slider[label] = gr.Slider(
                                        label=mod.mod_labels[label][0],
                                        value=mod.mod_labels[label][1],
                                        minimum=-1000 if mod.mod_allow_negative else 0,
                                        maximum=1000,
                                        step=1,
                                    )
                                    mod_slider[label].change(fn=update_tts_mod_value, inputs=mod_slider[label])

                gr.Markdown("### Please keep this tab open to keep JavaScript happy.")
            gr.Markdown("https://github.com/yownas/text-to-slop")

        with gr.Column():
            js_command = gr.Textbox(
                value = "",
                elem_id = "js_command",
                visible = 'hidden',
            )
            def run_js_command(argv):
                global queue_list

                play = gr.update()
                args = argv.split(' ', 1)
                if len(args) == 2:
                    if args[0] == 'play':
                        play = gr.update(
                            label=str(Path(args[1]).name),
                            value=args[1],
                        )
                    elif args[0] == 'skip':
                        # Remove queued item that match timestamp
                        queue_list = [item for item in queue_list if int(item[0]) != int(args[1])]
                    elif args[0] == 'toggleok':
                        for i, item in enumerate(queue_list):
                            if int(queue_list[i][0]) == int(args[1]):
                                queue_list[i][4] = not queue_list[i][4]
                                break

                return [
                    gr.update(value = ""),
                    play
                ]
            js_command.change(
                fn=run_js_command,
                inputs=[js_command],
                outputs=[js_command, slop_voice],
            )
            requests_check = gr.Checkbox(label = "Request queue", value = True)
            table = gr.HTML()
            gr.Markdown("## Played:")
            played = gr.HTML()

            queue_timer = gr.Timer(0.3)
            timer = gr.Timer(1)
            queue_name = gr.State("")
            queue_text = gr.State("")

    queue_timer.tick(
        fn=update_queue,
        outputs=[table, played],
    )
    timer.tick(
        fn=get_items,
        inputs=[requests_check, queue_text],
        outputs=[queue_name, queue_text, hidden_trigger]
    )
    # fill on page load
    hook_js = """
() => {
  window.js_command = (text) => {
    const el = document.querySelector('#js_command textarea, #js_command input');
    if (!el) return;
    el.value = text;
    el.dispatchEvent(new Event('input', {bubbles: true}));
  };
}
"""
    webui.load(
        fn=get_items,
        inputs=[requests_check, queue_text],
        outputs=[queue_name, queue_text, hidden_trigger],
        js=hook_js,
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
