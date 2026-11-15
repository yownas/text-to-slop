import torch
import os
from pathlib import Path
import soundfile as sf
from sympy.logic.boolalg import BooleanAtom
from qwen_tts import Qwen3TTSModel

class TTS():
    def __init__(self):
        self.ref_audio = None
        self.ref_text = None
        self.ref_vcp = None
        self.max_len = 200
        self.language = 'English'
        self.model = Qwen3TTSModel.from_pretrained("models/Qwen3-TTS-12Hz-0.6B-Base")

    def get_max_len(self):
        return self.max_len

    def set_max_len(self, max_len):
        self.max_len = max_len

    def get_language(self):
        return self.language

    def set_language(self, language):
        self.language = language

    def load_reference(self, sound):
        self.ref_audio = Path(os.getcwd()) / 'reference' / sound

        txt_file = self.ref_audio.with_suffix('.txt')
        if txt_file.exists():
            with open(txt_file, 'r', encoding='utf-8') as file:
                self.ref_text = file.read()
        else:
            text = Path(self.ref_audio.stem).with_suffix('')
            self.ref_text = str(text).replace("_", " ")

        self.ref_vcp = self.model.create_voice_clone_prompt(
            ref_audio = str(self.ref_audio),
            ref_text = self.ref_text,
        )


    def clone_voice(self, text):
        wavs, sr = self.model.generate_voice_clone(
            voice_clone_prompt = self.ref_vcp,
            language = self.language,
            text = text[:self.max_len]
        )
        return (sr, wavs[0])
