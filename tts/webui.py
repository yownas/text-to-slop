import gradio as gr
import time
from tts.qwen3tts import TTS

tts = TTS()

tts.load_reference("I_ve_got_balls_of_steel.mp3")

with gr.Blocks() as webui:
    gr.Markdown(
        """
        Text-To-Slop...
        """
    )

    slop_voice = gr.Audio(
        autoplay = True,
    )

    input_text = gr.Text()

    input_text.submit(fn=tts.clone_voice, inputs=input_text, outputs=slop_voice)


_, url, _ = webui.launch(
    allowed_paths=["."],
    prevent_thread_lock=True,
)

while True:
    time.sleep(100)

