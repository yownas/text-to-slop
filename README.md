# Local text-to-slop-speech

Local TTS for streamers who don't like cloud services.

# Installation

Download [start.ps1](https://raw.githubusercontent.com/yownas/text-to-slop/refs/heads/main/start.ps1) to an empty folder, right-click on it and select "Run with PowerShell".

If it fails you might need to open up a PowerShell and run `Set-ExecutionPolicy Unrestricted -Scope CurrentUser`
which hopefully will allow you to run it. (I hate Windows)
You will probably also need Microsoft Visual C++ Redistributable from https://aka.ms/vs/17/release/vc_redist.x64.exe

Then, inside the menu, select python. Download TTS. Run.

Place a 3-15 second audio clip in the `reference` folder. You also need to provide the transcript of what is spoken.
You can either name the file audio file with the phrase in its name `I_cant_run_through_the_mud_in_my_pretty_party_dress.mp3`
or create a `.txt` file with the same name as the audio file, containing the transcript.

# Submitting text via http

Firebot example.

### Play sound in the webui

`http://127.0.0.1:7860/submit?user=$encodeForUrl[$user]&text=$encodeForUrl[$arg[all]]&rnd=$randomUUID`

### Retrieve the soundclip to play in Firebot

`http://127.0.0.1:7860/sound?user=$user&text=$encodeForUrl[$chatMessage]&rnd=$randomUUID`

# Usage

* You *MUST* keep the browser tab open, or it might not play submitted texts in the browser.
* The text-to-speech server can run on a separate computer but audio will be played via the browser.

* The `Request queue` checkbox enable/disable processing of the queue.
* Clicking the litter bin icon will remove the request from the list.
* The thumbs up/red X toggle will allow the item to be processed. Items that hasn't been auto-approved will stay in the queue.

# Saftey and moderation

All messages will be stuck in the "Request queue" until they are deleted or approved.

TTS uses [Vrandan/Comment-Moderation](https://huggingface.co/Vrandan/Comment-Moderation) to classify text messages and can approve messages if enabled.

You can also add txt-files to `config/blocklists/` with one word per line that will be blocked. [google-profanity-words](https://github.com/coffee-and-fun/google-profanity-words/tree/main/data)
is a good start if you want pre-made list. The name of the file isn't important as long as it has a .txt suffix. All .txt files will be read and used.

Blocked users can be put in .txt-files in `config/userbans`. One username per line. As with wordlists, you can have multiple files.

