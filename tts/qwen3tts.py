from datetime import datetime
from hashlib import sha256
import os
from pathlib import Path
import threading

import soundfile as sf
from sympy.logic.boolalg import BooleanAtom
from qwen_tts import Qwen3TTSModel
from slugify import slugify
import torch
from transformers.utils import logging as hf_logging
hf_logging.set_verbosity_error()

class TTS():
    """ Class for text-to-slop """
    def __init__(self):
        self.ref_audio = None
        self.ref_text = None
        self.ref_vcp = None
        self.max_len = 500
        self.max_tokens = 1000
        self.language = 'English'
        self.tts_temperature = 0.9
        self.tts_top_p = 1.0
        self.tts_top_k = 50
        self.device = "cpu"
        self.cache = {}
        self.cache_lock = threading.Lock()
        if torch.cuda.is_available():
            self.device = "cuda"
        elif torch.backends.mps.is_available():
            self.device = "mps"
        elif hasattr(torch, "xpu") and torch.xpu.is_available():
            self.device = "xpu"
        else:
            self.device = "cpu"

        self.model = Qwen3TTSModel.from_pretrained(
            "models/Qwen3-TTS-12Hz-0.6B-Base",
            device_map=self.device,
        )

    # get/set functions
    def get_max_len(self): return self.max_len
    def set_max_len(self, max_len): self.max_len = max_len

    def get_max_tokens(self): return self.max_tokens
    def set_max_tokens(self, max_tokens): self.max_tokens = max_tokens

    def get_language(self): return self.language
    def set_language(self, language):
        self.language = language
        self.load_reference(self.ref_audio) # Re-load reference voice

    def get_tts_temperature(self): return self.tts_temperature
    def set_tts_temperature(self, tts_temperature): self.tts_temperature = tts_temperature

    def get_tts_top_p(self): return self.tts_top_p
    def set_tts_top_p(self, top_p): self.tts_top_p = top_p

    def get_tts_top_k(self): return self.tts_top_k
    def set_tts_top_k(self, top_k): self.tts_top_k = top_k


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

    def clone_voice(self, text, user="Anonymous"):
        """ Generate audio from text """
        with self.cache_lock:
            filehash = sha256(
                f"{slugify(text)}|{self.ref_audio}|{self.language}|{self.tts_temperature}|{self.tts_top_p}|{self.tts_top_k}"
                .encode('utf-8')
            ).hexdigest()
            if filehash in self.cache:
                filename = self.cache[filehash]
            else:
                print(f"Generating: {user}: {text[:self.max_len]}")
                wavs, sr = self.model.generate_voice_clone(
                    voice_clone_prompt = self.ref_vcp,
                    language = self.language,
                    text = text[:self.max_len],
                    x_vector_only_mode = True,
                    max_new_tokens = self.max_tokens,
                    non_streaming_mode = True,
                    temperature = float(self.tts_temperature), # 0.0 - 2.0, def 0.9 (consistent -> natural)
                    top_k = int(self.tts_top_k), # 1 - 3072, def 50 
                    top_p = float(self.tts_top_p), # 0.0 - 1.0, def 1.0 
                )
                output = Path(os.getcwd()) / 'output'
                filename = slugify(f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{text[:20]}") + ".mp3"
                path = str(output / filename)
                sf.write(path, wavs[0], sr, format="MP3")
                self.cache[filehash] = path
        return filename
