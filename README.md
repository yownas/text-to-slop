# Local text-to-speech

Local TTS for streamers who don't like cloud services.

# Installation

Put `start.ps1` in an empty folder and run it.
Select python. Download TTS. Run.

Place a ~3-5 second audio clip in the `reference` folder. You also need to provide the transcript of what is spoken.
You can either name the file audio file with the phrase in its name `I_m_getting_mud_on_my_pretty_party_dress.mp3`
or create a `.txt` file with the same name as the audio file, containing the transcript.

# Submitting text via http

Firebot example.

`http://127.0.0.1:7860/submit?user=$encodeForUrl[$user]&text=$encodeForUrl[$arg[all]]`

Method: GET

# Usage

* You *MUST* keep the browser tab open, or it won't play submitted texts.
* The text-to-speech server can run on a separate computer but audio will be played via the browser.

