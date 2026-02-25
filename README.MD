# Proposal

The proposal of this project it's simple: learn and play with audio, creating new sounds for testing headphones, sound systems or even to create some sound to play with others.
I'm using GEMINI to create the python scripts to generate new sounds/audios.

## Linux/Mint Instructions

```bash
sudo apt update
sudo apt install python3 python3-pip ffmpeg -y
sudo apt install python3-full -y
python3 -m venv .venv
source .venv/bin/activate
pip3 install requests numpy pydub pygame
```

## Running

```bash
source .venv/bin/activate
python3 imersive_rain.py
```

## Recommended Websites


https://freesound.org/

- Create an account
- Create an API KEY here: https://freesound.org/apiv2/apply/

https://sound-effects.bbcrewind.co.uk/