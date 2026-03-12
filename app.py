"""
Main entry point.

Starts:
  1. Flask web server (admin UI + guest request page) in a background thread
  2. Display loop in the main thread — polls Spotify and refreshes e-ink on track change
"""

import os
import threading
import time
import qrcode
from PIL import Image

from flask import Flask, render_template, request, redirect, url_for, jsonify

import config
import spotify_service as svc
import display_service as display_svc
from display.eink_driver import EinkDisplay

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__, template_folder="web/templates", static_folder="web/static")
app.secret_key = config.FLASK_SECRET_KEY

sp = svc.get_spotify_client()
eink = EinkDisplay()

_state: dict = {
    "current_track": None,
    "guest_requests_enabled": config.GUEST_REQUESTS_ENABLED,
    "request_queue": [],
    "playlist": None,   # {"id": str, "url": str}
}
_state_lock = threading.Lock()


# ---------------------------------------------------------------------------
# QR helpers
# ---------------------------------------------------------------------------

def _generate_qr(url: str, output_path: str, box_size: int = 10, border: int = 2):
    qr = qrcode.QRCode(box_size=box_size, border=border,
                       error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(output_path)
    return output_path


def setup_collaborative_playlist():
    """Create (or load) the collaborative playlist and generate both QR files."""
    if not svc.is_authenticated(sp):
        return

    playlist = svc.ensure_collaborative_playlist(
        sp, config.COLLABORATIVE_PLAYLIST_NAME, config.PLAYLIST_CACHE_PATH
    )

    with _state_lock:
        _state["playlist"] = playlist

    # QR for web admin UI (larger)
    _generate_qr(playlist["url"], config.QR_CODE_PATH, box_size=10)
    # QR for e-ink overlay (smaller, tighter)
    _generate_qr(playlist["url"], config.QR_DISPLAY_PATH, box_size=4, border=1)

    print(f"[playlist] Collaborative playlist ready: {playlist['url']}")


# ---------------------------------------------------------------------------
# Web routes — Auth
# ---------------------------------------------------------------------------

@app.route("/login")
def login():
    auth_url = svc.get_auth_url(sp)
    print(f"[auth] Redirecting to: {auth_url}")
    return redirect(auth_url)


@app.route("/callback")
def callback():
    code = request.args.get("code")
    if code and svc.handle_callback(sp, code):
        setup_collaborative_playlist()
        return redirect(url_for("admin"))
    return "Authentication failed.", 400


# ---------------------------------------------------------------------------
# Web routes — Admin
# ---------------------------------------------------------------------------

@app.route("/")
@app.route("/admin")
def admin():
    authenticated = svc.is_authenticated(sp)
    with _state_lock:
        state = dict(_state)
    return render_template("admin.html", authenticated=authenticated, state=state)


@app.route("/admin/skip", methods=["POST"])
def admin_skip():
    svc.skip_track(sp)
    return redirect(url_for("admin"))


@app.route("/admin/toggle_requests", methods=["POST"])
def admin_toggle_requests():
    with _state_lock:
        _state["guest_requests_enabled"] = not _state["guest_requests_enabled"]
    return redirect(url_for("admin"))


@app.route("/admin/new-playlist", methods=["POST"])
def admin_new_playlist():
    """Delete cached playlist ID and create a fresh collaborative playlist."""
    if os.path.exists(config.PLAYLIST_CACHE_PATH):
        os.remove(config.PLAYLIST_CACHE_PATH)
    setup_collaborative_playlist()
    return redirect(url_for("admin"))


@app.route("/admin/queue/remove/<int:index>", methods=["POST"])
def admin_remove_from_queue(index: int):
    with _state_lock:
        if 0 <= index < len(_state["request_queue"]):
            _state["request_queue"].pop(index)
    return redirect(url_for("admin"))


@app.route("/api/status")
def api_status():
    with _state_lock:
        return jsonify({
            "current_track": _state["current_track"],
            "guest_requests_enabled": _state["guest_requests_enabled"],
            "queue_length": len(_state["request_queue"]),
            "playlist": _state["playlist"],
        })


# ---------------------------------------------------------------------------
# Display loop
# ---------------------------------------------------------------------------

def display_loop():
    last_track_id = None

    while True:
        try:
            authenticated = svc.is_authenticated(sp)

            if authenticated:
                track = svc.get_current_track(sp)

                with _state_lock:
                    _state["current_track"] = track

                current_id = (track["id"], track.get("is_playing")) if track else None

                if current_id != last_track_id:
                    qr_path = config.QR_DISPLAY_PATH if os.path.exists(config.QR_DISPLAY_PATH) else None

                    if track:
                        print(f"[display] {track['title']} — {track['artist']}")
                        image = display_svc.build_display_image(track, qr_path=qr_path)
                    else:
                        print("[display] Nothing playing.")
                        image = display_svc.build_idle_image(qr_path=qr_path)

                    eink.display(image)
                    last_track_id = current_id

        except Exception as e:
            print(f"[display] Error: {e}")

        time.sleep(config.DISPLAY_REFRESH_INTERVAL)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # If already authenticated from a previous run, set up playlist immediately
    if svc.is_authenticated(sp):
        setup_collaborative_playlist()

    display_thread = threading.Thread(target=display_loop, daemon=True)
    display_thread.start()

    print(f"[web] Starting Flask on {config.FLASK_HOST}:{config.FLASK_PORT}")
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=config.FLASK_DEBUG, use_reloader=False)
