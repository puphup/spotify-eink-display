import os
from dotenv import load_dotenv

load_dotenv()

# Spotify OAuth
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:5000/callback")
SPOTIFY_SCOPES = " ".join([
    "user-read-currently-playing",
    "user-read-playback-state",
    "playlist-modify-public",
    "playlist-modify-private",
])

# Flask
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "change-me-in-production")
FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"

# Display — 7.3" ACeP 7-color, portrait orientation (physical 800x480, rotated to 480x800)
DISPLAY_REFRESH_INTERVAL = int(os.getenv("DISPLAY_REFRESH_INTERVAL", 5))  # seconds between polls
EINK_WIDTH = int(os.getenv("EINK_WIDTH", 480))    # portrait width
EINK_HEIGHT = int(os.getenv("EINK_HEIGHT", 800))  # portrait height

# Collaborative playlist
COLLABORATIVE_PLAYLIST_NAME = os.getenv("COLLABORATIVE_PLAYLIST_NAME", "Café Song Requests")
GUEST_REQUESTS_ENABLED = os.getenv("GUEST_REQUESTS_ENABLED", "true").lower() == "true"

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, ".cache")
os.makedirs(CACHE_DIR, exist_ok=True)
SPOTIFY_CACHE_PATH = os.path.join(CACHE_DIR, ".spotify_token")
PLAYLIST_CACHE_PATH = os.path.join(CACHE_DIR, "playlist.json")
QR_CODE_PATH = os.path.join(BASE_DIR, "web", "static", "qr_code.png")  # web UI
QR_DISPLAY_PATH = os.path.join(CACHE_DIR, "qr_display.png")             # e-ink overlay
