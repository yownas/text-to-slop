from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import threading

import soundfile as sf
from sympy.logic.boolalg import BooleanAtom
from qwen_tts import Qwen3TTSModel
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from slugify import slugify
import torch
from transformers.utils import logging as hf_logging
hf_logging.set_verbosity_error()
import __main__

class TTS():
    """ Class for text-to-slop """
    def tts_load_config(self):
        path = Path(__main__.__file__).resolve().parent / 'config' / 'tts_config.json'
        json_opt = {}
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as file:
                    json_opt = json.load(file)
            except:
                pass
        for attr in self.opt_config.keys():
            setattr(self, attr, json_opt.get(attr, self.opt_config.get(attr, None)))

    def tts_save_config(self):
        json_opt = {}
        for attr in self.opt_config.keys():
            json_opt[attr] = getattr(self, attr, None)
        path = Path(__main__.__file__).resolve().parent / 'config' / 'tts_config.json'
        with open(path, "w", encoding="utf-8") as file:
            json.dump(json_opt, file, indent=4)

    def tts_set_device(self):
        if self.use_cpu:
            self.device = "cpu"
            return
        if torch.cuda.is_available():
            self.device = "cuda"
            return
        elif torch.backends.mps.is_available():
            self.device = "mps"
            return
        elif hasattr(torch, "xpu") and torch.xpu.is_available():
            self.device = "xpu"
            return
        self.device = "cpu"
        self.load_model()

    def load_model(self):
        self.model = Qwen3TTSModel.from_pretrained(
            Path(__main__.__file__).resolve().parent / 'models' / 'Qwen3-TTS-12Hz-0.6B-Base',
            device_map=self.device,
            dtype=torch.bfloat16,
        )

    def __init__(self):
        self.ref_vcp = None

        # Config options
        self.opt_config = {
            'max_len': 500,
            'max_tokens': 1000,
            'language': 'English',
            'tts_temperature': 0.9,
            'tts_top_p': 1.0,
            'tts_top_k': 50,
            'ref_audio': None,
            'ref_text': None,
            'use_cpu': False,
        }
        self.tts_load_config()
        self.tts_set_device()

        self.cache = {}
        self.cache_lock = threading.Lock()

        self.load_model()

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

    def get_use_cpu(self): return self.use_cpu
    def set_use_cpu(self, use_cpu):
        self.use_cpu = use_cpu
        self.tts_set_device()
        self.load_reference(self.ref_audio) # Re-load reference voice

    def load_reference(self, sound):
        """ Load reference sound file """
        self.ref_audio = str(Path(__main__.__file__).resolve().parent / 'reference' / sound)

        txt_file = Path(self.ref_audio).with_suffix('.txt')
        if txt_file.exists():
            with open(txt_file, 'r', encoding='utf-8') as file:
                self.ref_text = file.read()
        else:
            text = Path(Path(self.ref_audio).stem).with_suffix('')
            self.ref_text = str(text).replace("_", " ")

        self.ref_vcp = self.model.create_voice_clone_prompt(
            ref_audio = str(self.ref_audio),
            ref_text = self.ref_text,
            x_vector_only_mode = True
        )
        self.tts_save_config() # This is as good time as ever to save the config
        self.tts_set_device()

    def clone_voice(self, text, user="Anonymous"):
        """ Generate audio from text """
        self.tts_save_config() # This is as good time as ever to save the config
        with self.cache_lock:
            filehash = sha256(
                f"{text.strip()}|{self.ref_audio}|{self.language}|{self.tts_temperature}|{self.tts_top_p}|{self.tts_top_k}"
                .encode('utf-8')
            ).hexdigest()
            if filehash in self.cache and self.cache[filehash] is not None:
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
                if self.device == "cuda":
                    torch.cuda.empty_cache()
                output = Path(__main__.__file__).resolve().parent / 'output'
                filename = slugify(f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{text[:20]}") + ".mp3"
                filename = str(output / filename)
                sf.write(filename, wavs[0], sr, format="MP3")
            self.cache[filehash] = filename
        return filename
