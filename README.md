# Spotify E-Ink Display

A Raspberry Pi project that displays the currently playing Spotify track on a **Waveshare 7.3" ACeP 7-color e-ink screen**. Includes a guest song request page (via QR code) and an admin web UI.

![Display preview](docs/preview.png)

---

## Features

- Full-color album art on e-ink display (portrait orientation)
- Track title and artist overlay with multilingual support (Thai, Japanese, CJK, Arabic, Latin)
- Auto-refreshes only when the track changes
- Guest song request page accessible via QR code
- Admin web UI: skip tracks, enable/disable requests, manage queue
- Mock mode for development on non-Pi hardware (outputs PNG preview)

---

## Hardware

| Component | Recommended |
|-----------|------------|
| Raspberry Pi | Pi 4 (2GB+) |
| Display | Waveshare 7.3" ACeP 7-color e-Paper HAT |
| Storage | 16GB+ microSD |
| Power | Official Pi 4 USB-C PSU |

The display connects via SPI (GPIO header). See [Waveshare wiki](https://www.waveshare.com/wiki/7.3inch_e-Paper_HAT_(F)) for wiring details.

---

## Installation

### 1. Raspberry Pi OS setup

Flash **Raspberry Pi OS Lite (64-bit)** and enable SSH. Then:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip python3-venv git fonts-noto fonts-noto-cjk fonts-thai-tlwg -y
```

Enable SPI for the display:
```bash
sudo raspi-config
# Interface Options → SPI → Enable
```

### 2. Clone the repo

```bash
git clone https://github.com/puphup/spotify-eink-display.git
cd spotify-eink-display
```

### 3. Install Python dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Install Waveshare e-Paper library

```bash
git clone https://github.com/waveshare/e-Paper.git
pip install ./e-Paper/RaspberryPi_JetsonNano/python/
```

### 5. Configure environment

```bash
cp .env.example .env
nano .env
```

Fill in the required values:

```env
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8080/callback
FLASK_SECRET_KEY=a-random-secret-string
FLASK_PORT=8080
EINK_MOCK=false        # set true for dev/testing on non-Pi
```

### 6. Register a Spotify Developer App

1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Create an app
3. Add redirect URI: `http://127.0.0.1:8080/callback` (click **Add** then **Save**)
4. Copy **Client ID** and **Client Secret** into `.env`

### 7. Run

```bash
source venv/bin/activate
python app.py
```

Open `http://<pi-ip>:8080/admin` in a browser and click **Connect Spotify** to authenticate.

---

## Running on startup (systemd)

Create `/etc/systemd/system/spotify-display.service`:

```ini
[Unit]
Description=Spotify E-Ink Display
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/spotify-eink-display
ExecStart=/home/pi/spotify-eink-display/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable it:
```bash
sudo systemctl enable spotify-display
sudo systemctl start spotify-display
```

---

## Development (macOS / non-Pi)

Set `EINK_MOCK=true` in `.env`. The display output is saved as a PNG at:

```
.cache/last_display.png
```

---

## Project structure

```
spotify-display/
├── app.py                  # Flask server + display loop
├── config.py               # Config from .env
├── spotify_service.py      # Spotify API (auth, now-playing, search, queue)
├── display_service.py      # Image composition (album art + text overlay)
├── display/
│   └── eink_driver.py      # Waveshare 7.3" ACeP driver wrapper
├── web/
│   ├── templates/          # Jinja2 HTML templates
│   └── static/css/         # Stylesheet
├── requirements.txt
└── .env.example
```

---

## Web UI

| URL | Description |
|-----|-------------|
| `/admin` | Admin dashboard (skip, queue, toggle requests) |
| `/request` | Guest song request page |
| `/api/status` | JSON status endpoint |

---

## License

MIT
