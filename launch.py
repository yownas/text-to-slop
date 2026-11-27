import logging
import os
from pathlib import Path
import subprocess
import sys
import __main__

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

    requirements_file = Path(__main__.__file__).resolve().parent / "pre_requirements_versions.txt"

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
    requirements_file = Path(__main__.__file__).resolve().parent / "requirements_versions.txt"
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
        (
            "Vrandan/Comment-Moderation",
            "./vrandan-comment-moderation",
        ),
    ]
    for repo, local_dir in model_repos:
        path = Path(__main__.__file__).resolve().parent / 'models' / local_dir
        print(f"Download {repo}")
        snapshot_download(repo_id=repo, local_dir=path)

def get_flash_attn():
    import importlib.util
    import platform
    import re
    import subprocess
    import sys
    import sysconfig
    import urllib.request
    import torch

    if importlib.util.find_spec("flash_attn"):
        return True

    PACKAGES_URL = (
        "https://raw.githubusercontent.com/mjun0812/flash-attention-prebuild-wheels/"
        "refs/heads/main/doc/packages.md"
    )
    RELEASE_BASE = "https://github.com/mjun0812/flash-attention-prebuild-wheels/releases/download"

    _URL_RE = re.compile(
        r"https://github\.com/mjun0812/flash-attention-prebuild-wheels/releases/download/"
        r"(v[\d.]+)/([^\s)\],]+\.whl)"
    )
    # flash_attn-2.8.3+cu126torch2.14-cp313-cp313-linux_x86_64.whl
    _NAME_RE = re.compile(
        r"^(?P<pkg>[A-Za-z0-9_]+)-(?P<ver>[^+-]+)\+(?P<accel>cu|rocm)(?P<accver>[\d.]+?)"
        r"torch(?P<torch>\d+\.\d+)(?P<rest>[^-]*)-(?P<py>cp\d+t?)-(?P<abi>[^-]+)-(?P<plat>.+)\.whl$"
    )


    def _vkey(s):
        """'2.7.4.post1' / 'v0.10.0' -> comparable tuple of ints."""
        return tuple(int(x) for x in re.findall(r"\d+", s))

    def _platform_ok(plat):
        machine = platform.machine().lower()
        if sys.platform.startswith("linux"):
            arch = "aarch64" if machine in ("aarch64", "arm64") else "x86_64"
            return "linux" in plat and arch in plat
        if sys.platform == "win32":
            return plat.startswith("win_amd64")
        return False


    def find_flash_attn_wheel(cuda_fallback=False, packages_url=PACKAGES_URL):
        """Return the URL of the best prebuilt flash_attn wheel for this environment, or None.

        Must match exactly: Python (incl. free-threaded 't'), torch major.minor,
        OS/arch, and CUDA/ROCm version. Among matches, prefers the newest
        flash-attn version, then the newest repo release tag.

        cuda_fallback=True also accepts a wheel built for the same CUDA major with a
        lower minor version (e.g. cu124 wheel for cu126 torch). Usually works, not guaranteed.
        """
        if torch.version.hip:
            accel = "rocm"
            accver = "".join(re.match(r"(\d+)\.(\d+)", torch.version.hip).groups())
        elif torch.version.cuda:
            accel = "cu"
            accver = torch.version.cuda.replace(".", "")
        else:
            return None  # CPU-only torch: no flash-attn wheel applies

        torch_mm = ".".join(re.match(r"(\d+)\.(\d+)", torch.__version__).groups())
        gil_off = bool(sysconfig.get_config_var("Py_GIL_DISABLED"))
        py_tag = f"cp{sys.version_info.major}{sys.version_info.minor}{'t' if gil_off else ''}"

        req = urllib.request.Request(packages_url, headers={"User-Agent": "flash-attn-wheel-finder"})
        text = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")

        best_key, best_url = None, None
        for tag, fname in set(_URL_RE.findall(text)):
            m = _NAME_RE.match(fname)
            if not m or m["pkg"] != "flash_attn":
                continue
            if m["accel"] != accel or m["torch"] != torch_mm:
                continue
            if m["py"] != py_tag or m["abi"] != py_tag or not _platform_ok(m["plat"]):
                continue

            av = m["accver"].replace(".", "")
            if av == accver:
                exact = 1
            elif cuda_fallback and accel == "cu" and av[:-1] == accver[:-1] and av < accver:
                exact = 0
            else:
                continue

            key = (exact, av, _vkey(m["ver"]), _vkey(tag), m["plat"].startswith("linux_"))
            if best_key is None or key > best_key:
                best_key, best_url = key, f"{RELEASE_BASE}/{tag}/{fname}"
        return best_url

    wheel = find_flash_attn_wheel()
    if wheel is not None:
        run(
            f'"{sys.executable}" -m pip install "{wheel}"',
            "Installing matching flash-attn",
            "Failed flash-attn installation",
        )


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
    get_flash_attn()
except Exception as e:
    pass

try:
    download_models()
except Exception as e:
    log.warning("model download failed: %s", e)

def launch_ui():
    from tts.webui import launch_me
    launch_me()
    print("Exit")

print("Launch webui")
launch_ui()

