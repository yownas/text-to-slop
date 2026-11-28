from datetime import datetime
from hashlib import sha256
import json
import logging
import os
from pathlib import Path
import re
import threading
import sys

import soundfile as sf
from sympy.logic.boolalg import BooleanAtom
from slugify import slugify
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from transformers.utils import logging as hf_logging
hf_logging.set_verbosity_error()
import __main__

class MOD():
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
        self.tts_set_device()

    def __init__(self):
        # Config options
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
            "mod_allow_negative": False,
            "mod_labels": {
                "OK": ["Appropriate content", 9999, False],
                "H": ["Hate", 100, True],
                "SH": ["Self-harm", 100, True],
                "V": ["Violence", 100, True],
                "S": ["Sexual", 100, True],
                "HR": ["Harassment", 100, True],
                "V2": ["Violence/Graphic", 100, True],
                "S3": ["Sexual/Minors", 100, True],
                "H2": ["Hate/Threat", 100, True],
            }
        }
        self.mod_load_config()
        self.mod_meaning_labels = {v[0]: k for k, v in self.mod_labels.items()} # Reverse lookup
        self.mod_re_pattern = self.get_mod_re_pattern()
        self.mod_banned_users = self.get_mod_banned_users()

        # mod logfile
        output = Path(__main__.__file__).resolve().parent / 'output'
        filename = "modlog_" + str(f"{datetime.now().strftime('%Y-%m-%dT%H_%M_%S')}") + ".txt"
        filename = str(output / filename)
        file_handler = logging.FileHandler(filename, mode="a", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(logging.DEBUG)
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(stdout_handler)
        self.logger.addHandler(file_handler)
        self.logger.setLevel(logging.DEBUG)
        self.logger.info(f"Started logfile: {filename}")

    # get/set functions
    def set_mod_enabled(self, state):
        self.mod_enabled = state
        self.mod_save_config()

    def set_mod_level(self, label, value):
        self.mod_labels[label][1] = value
        self.mod_save_config()

    def mod_block_user(self, username):
        if len(username) > 0:
            path = Path(__main__.__file__).resolve().parent / 'config' / 'userbans' / f"{slugify(username)}.txt"
            with open(path, "w", encoding="utf-8") as file:
                file.write(f"{username}\n")
        self.mod_reload()

    def moderate_text(self, text, user=None):
        self.logger.info(f"\nModeration: Check: {text}")

        if user.lower() in self.mod_banned_users:
            self.logger.info(f"{user} is banned.")
            return False

        if self.mod_re_pattern is not None:
            blocklist_words = self.mod_re_pattern.search(text)
            if blocklist_words is not None:
                self.logger.info(f"BLOCKED by word list: {blocklist_words.group()}")
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
                status = int(predictions.get(key, 0) * 1000) <= self.mod_labels.get(key, [0,0])[1]
                pass_mod = pass_mod if status else status
                self.logger.info(f"    [{' OK ' if status else 'FAIL'}]  {self.mod_labels.get(key, ['???'])[0]:<20} {int(predictions.get(key, 0) * 1000):>4d}")

        if not self.mod_enabled:
            # If auto moderations isn't enabled, just block everything
            return False

        return pass_mod
