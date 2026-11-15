import logging
import os
from pathlib import Path
import subprocess
import sys

log = logging.getLogger(__name__)

def run(command, desc=None, errdesc=None) -> str:
    if desc is not None:
        print(desc)

    run_kwargs = {
        "args": command,
        "shell": True,
        "env": os.environ,
        "encoding": "utf8",
        "errors": "ignore",
    }

#    if not live:
#        run_kwargs["stdout"] = run_kwargs["stderr"] = subprocess.PIPE

    result = subprocess.run(**run_kwargs)

    if result.returncode != 0:
        error_bits = [
            f"{errdesc or 'Error running command'}.",
            f"Command: {command}",
            f"Error code: {result.returncode}",
        ]
        if result.stdout:
            error_bits.append(f"stdout: {result.stdout}")
        if result.stderr:
            error_bits.append(f"stderr: {result.stderr}")
        raise RuntimeError("\n".join(error_bits))

    return result.stdout or ""

def prepare_env():
    print(f"Python {sys.version}")

    requirements_file = "pre_requirements_versions.txt"

    run(
        f'"{sys.executable}" -m pip install --upgrade pip',
        "Check pip",
        "Couldn't check pip",
    )
    run(
        f'"{sys.executable}" -m pip install --no-warn-script-location -r "{requirements_file}"',
        "Check pre-requirements",
        "Couldn't check pre-requirements",
    )

def prepare_modules():
    requirements_file = "requirements_versions.txt"
    run(
        f'"{sys.executable}" -m pip install --no-warn-script-location --no-build-isolation -r "{requirements_file}"',
        "Check requirements",
        "Couldn't check requirements",
    )

def get_torch():
    from torchvisir import Torchvisir
    print("Install torch...")
    print(Torchvisir().install_torch())

def download_models():
    from huggingface_hub import snapshot_download

    model_repos = [
        (
            "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
            "./Qwen3-TTS-12Hz-0.6B-Base",
        ),
#        (
#            "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
#            "./Qwen3-TTS-12Hz-1.7B-Base",
#        ),
    ]

    for repo, local_dir in model_repos:
        path = Path(__file__).resolve().parent / 'models' / local_dir
        print(f"Download {repo}")
        snapshot_download(repo_id=repo, local_dir=path)

try:
    prepare_env()
except Exception as e:
    log.warning("python setup failed: %s", e)

try:
    get_torch()
except Exception as e:
    log.warning("torch failed: %s", e)

try:
    prepare_modules()
except Exception as e:
    log.warning("python modules failed: %s", e)

try:
    download_models()
except Exception as e:
    log.warning("model download failed: %s", e)

def launch_ui():
    from tts.webui import launch_me
    launch_me()
    print("Exit")

print("Lauch webui")
launch_ui()

