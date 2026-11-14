# Local text-to-speech

Local TTS for streamers who don't like cloud services.

# Installation

Put `start.ps1` in an empty folder and run it.
Select python. Download TTS. Run.

Place a ~3 second audio clip in the `reference` folder. You also need to provide with the phrase spoken in the sound file.
You can either name the file with the content, like `I_m_getting_mud_on_my_pretty_party_dress.mp3` or create a `.txt` file
with the same name as the audio file, containing the phrase.

# Submitting text via http

Firebot example.

`http://127.0.0.1:7860/submit?text=$encodeForUrl[$arg[all]]`
