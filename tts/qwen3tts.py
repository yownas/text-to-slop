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
    def get_mod_re_pattern(self):
        folder = Path(__main__.__file__).resolve().parent / 'config' / 'blocklists'
        blocked = set()
        for ext in ("txt",):
            for file in Path(folder).glob(f"*.{ext}"):
                try:
                    with open(file, 'r', encoding='utf-8') as blocklist:
                        for line in blocklist:
                            blocked.add(line.strip())
                except:
                    pass

        if len(blocked) > 0:
            pattern = re.compile(
                r"(?<!\w)(?:" + "|".join(map(re.escape, sorted(blocked, key=len, reverse=True))) + r")(?!\w)",
                re.IGNORECASE,
            )
        else:
            pattern = None
        return pattern

    def get_mod_banned_users(self):
        folder = Path(__main__.__file__).resolve().parent / 'config' / 'userbans'
        banned = set()
        for ext in ("txt",):
            for file in Path(folder).glob(f"*.{ext}"):
                try:
                    with open(file, 'r', encoding='utf-8') as userban:
                        for line in userban:
                            banned.add(line.strip().lower())
                except:
                    pass
        return list(banned)

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

    def mod_load_config(self):
        path = Path(__main__.__file__).resolve().parent / 'config' / 'mod_config.json'
        json_opt = {}
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as file:
                    json_opt = json.load(file)
            except:
                pass
        for attr in self.mod_config.keys():
            setattr(self, attr, json_opt.get(attr, self.mod_config.get(attr, None)))

    def mod_save_config(self):
        json_opt = {}
        for attr in self.mod_config.keys():
            json_opt[attr] = getattr(self, attr, None)
        path = Path(__main__.__file__).resolve().parent / 'config' / 'mod_config.json'
        with open(path, "w", encoding="utf-8") as file:
            json.dump(json_opt, file, indent=4)

    def mod_reload(self):
        self.mod_re_pattern = self.get_mod_re_pattern()
        self.mod_banned_users = self.get_mod_banned_users()
        self.tts_save_config() # Save this as well just for good measure
        self.mod_save_config()

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
        }
        self.tts_load_config()

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
            Path(__main__.__file__).resolve().parent / 'models' / 'Qwen3-TTS-12Hz-0.6B-Base',
            device_map=self.device,
        )
        self.mod_model = AutoModelForSequenceClassification.from_pretrained(
            Path(__main__.__file__).resolve().parent / 'models' / 'vrandan-comment-moderation',
            device_map="cpu",
        )
        self.mod_tokenizer = AutoTokenizer.from_pretrained(
            Path(__main__.__file__).resolve().parent / 'models' / 'vrandan-comment-moderation',
            device_map="cpu",
        )

        # Moderation options
        self.mod_config = {
            "mod_enabled": True,
            "mod_verbose": True,
            "mod_allow_negative": False,
            "mod_labels": {
                "OK": ["Appropriate content", 0.9, False],
                "H": ["Hate", 0.1, True],
                "SH": ["Self-harm", 0.1, True],
                "V": ["Violence", 0.1, True],
                "S": ["Sexual", 0.1, True],
                "HR": ["Harassment", 0.1, True],
                "V2": ["Violence/Graphic", 0.1, True],
                "S3": ["Sexual/Minors", 0.1, True],
                "H2": ["Hate/Threat", 0.1, True],
            }
        }
        self.mod_load_config()
        self.mod_meaning_labels = {v[0]: k for k, v in self.mod_labels.items()} # Reverse lookup
        self.mod_re_pattern = self.get_mod_re_pattern()
        self.mod_banned_users = self.get_mod_banned_users()

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
        self.ref_audio = str(Path(__main__.__file__).resolve().parent / 'reference' / sound)

        txt_file = Path(self.ref_audio).with_suffix('.txt')
        if txt_file.exists():
            with open(txt_file, 'r', encoding='utf-8') as file:
                self.ref_text = file.read()
        else:
            text = Path(self.ref_audio.stem).with_suffix('')
            self.ref_text = str(text).replace("_", " ")

        self.ref_vcp = self.model.create_voice_clone_prompt(
            ref_audio = str(self.ref_audio),
            ref_text = self.ref_text,
            x_vector_only_mode = True
        )
        self.tts_save_config() # This is as good time as ever to save the config
        self.mod_save_config()

    def set_mod_enabled(self, state):
        self.mod_enabled = state

    def set_mod_verbose(self, state):
        self.mod_verbose = state

    def set_mod_level(self, label, value):
        self.mod_labels[label][1] = value

    def mod_block_user(self, username):
        if len(username) > 0:
            path = Path(__main__.__file__).resolve().parent / 'config' / 'userbans' / f"{slugify(username)}.txt"
            with open(path, "w", encoding="utf-8") as file:
                file.write(f"{username}\n")
        self.mod_reload()

    def moderate_text(self, text, user=None, verbose=False):
        if not self.mod_enabled:
            # If moderations isn't enabled, just allow anything
            return True

        if verbose: print(f"\nModeration: Check: {text}")

        if user.lower() in self.mod_banned_users:
            print(f"{user} is banned.")
            return False

        if self.mod_re_pattern is not None:
            blocklist_words = self.mod_re_pattern.search(text)
            if blocklist_words is not None:
                if verbose: print(f"BLOCKED by word list: {blocklist_words.group()}")
                return False

        # Use classifier
        inputs = self.mod_tokenizer(text, return_tensors="pt")
        outputs = self.mod_model(**inputs)
        probabilities = outputs.logits.softmax(dim=-1).squeeze()

        # Get predictions
        labels = [self.mod_model.config.id2label[i] for i in range(len(probabilities))]
        predictions = dict(zip(labels, probabilities.detach().tolist()))

        pass_mod = True
        for key in self.mod_labels.keys():
            if self.mod_labels.get(key, [0,0,False])[2]:
                status = predictions.get(key, 0.0) <= self.mod_labels.get(key, [0,0.0])[1]
                pass_mod = pass_mod if status else status
                if verbose:
                    print(f"[{' OK ' if status else 'FAIL'}]  {self.mod_labels.get(key, ['???'])[0]:<20} {predictions.get(key, 0.0):.4f}")

        return pass_mod

    def clone_voice(self, text, user="Anonymous"):
        """ Generate audio from text """
        self.tts_save_config() # This is as good time as ever to save the config
        self.mod_save_config()
        with self.cache_lock:
            filehash = sha256(
                f"{text.strip()}|{self.ref_audio}|{self.language}|{self.tts_temperature}|{self.tts_top_p}|{self.tts_top_k}"
                .encode('utf-8')
            ).hexdigest()
            if filehash in self.cache and self.cache[filehash] is not None:
                filename = self.cache[filehash]
            else:
                if self.moderate_text(text, user=user, verbose=self.mod_verbose):
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
                    output = Path(__main__.__file__).resolve().parent / 'output'
                    filename = slugify(f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{text[:20]}") + ".mp3"
                    filename = str(output / filename)
                    sf.write(filename, wavs[0], sr, format="MP3")
                else:
                    filename = None
                self.cache[filehash] = filename
        return filename
