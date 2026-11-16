# Local text-to-speech

Local TTS for streamers who don't like cloud services.

# Installation

Download [start.ps1](https://raw.githubusercontent.com/yownas/text-to-slop/refs/heads/main/start.ps1) to an empty folder, right-click on it and select "Run with PowerShell".
If it fails you might need to open up PowerShell and run `Set-ExecutionPolicy Unrestricted -Scope CurrentUser`
which hopefully will allow you to run it. (I hate Windows)
Select python. Download TTS. Run.

Place a ~3-5 second audio clip in the `reference` folder. You also need to provide the transcript of what is spoken.
You can either name the file audio file with the phrase in its name `I_cant_run_through_the_mud_in_my_pretty_party_dress.mp3`
or create a `.txt` file with the same name as the audio file, containing the transcript.

# Submitting text via http

Firebot example.

### Play sound in the webui

`http://127.0.0.1:7860/submit?user=$encodeForUrl[$user]&text=$encodeForUrl[$arg[all]]&rnd=$randomUUID`

### Retrieve the soundclip to play it in Firebot

`http://127.0.0.1:7860/sound?user=$user&text=$encodeForUrl[$chatMessage]&rnd=$randomUUID`


# Usage

* You *MUST* keep the browser tab open, or it won't play submitted texts.
* The text-to-speech server can run on a separate computer but audio will be played via the browser.

