from datetime import datetime
import os
from pathlib import Path

import soundfile as sf
from sympy.logic.boolalg import BooleanAtom
from qwen_tts import Qwen3TTSModel
from slugify import slugify
from transformers.utils import logging as hf_logging
hf_logging.set_verbosity_error()

class TTS():
    """ Class for text-to-slop """
    def __init__(self):
        self.ref_audio = None
        self.ref_text = None
        self.ref_vcp = None
        self.max_len = 200
        self.max_tokens = 500
        self.language = 'English'
        self.model = Qwen3TTSModel.from_pretrained(
            "models/Qwen3-TTS-12Hz-0.6B-Base",
            device_map="cuda:0",
        )

    def get_max_len(self):
        """ Get max length for text input """
        return self.max_len

    def set_max_len(self, max_len):
        """ Set max length for text input """
        self.max_len = max_len

    def get_max_tokens(self):
        """ Get max tokens for audio output """
        return self.max_tokens

    def set_max_tokens(self, max_tokens):
        """ Set max tokens for audio output """
        self.max_tokens = max_tokens

    def get_language(self):
        """ Get language """
        return self.language

    def set_language(self, language):
        """ Set language """
        self.language = language
        self.load_reference(self.ref_audio) # Re-load reference voice

    def load_reference(self, sound):
        """ Load reference sound file """
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
            x_vector_only_mode = True,
        )

    def clone_voice(self, text):
        """ Generate audio from text """
        wavs, sr = self.model.generate_voice_clone(
            voice_clone_prompt = self.ref_vcp,
            language = self.language,
            text = text[:self.max_len],
            x_vector_only_mode = True,
            max_new_tokens = self.max_tokens,
            non_streaming_mode = True,
        )
        output = Path(os.getcwd()) / 'output'
        filename = slugify(f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{text[:20]}") + ".mp3"
        path = str(output / filename)
        sf.write(path, wavs[0], sr, format="MP3")

        return filename
