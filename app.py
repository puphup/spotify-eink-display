"""
Main entry point.

Starts:
  1. Flask web server (admin UI + guest request page) in a background thread
  2. Display loop in the main thread — polls Spotify and refreshes e-ink on track change
"""

import threading
import time
import qrcode

from flask import Flask, render_template, request, redirect, url_for, jsonify, session

import config
import spotify_service as svc
import display_service as display_svc
from display.eink_driver import EinkDisplay

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__, template_folder="web/templates", static_folder="web/static")
app.secret_key = config.FLASK_SECRET_KEY

# Shared Spotify client (initialised once; thread-safe for reads)
sp = svc.get_spotify_client()
eink = EinkDisplay()

# In-memory state shared between display loop and web routes
_state: dict = {
    "current_track": None,
    "guest_requests_enabled": config.GUEST_REQUESTS_ENABLED,
    "request_queue": [],  # list of {title, artist, uri, requester}
}
_state_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def generate_qr_code():
    request_url = f"http://raspberrypi.local:{config.FLASK_PORT}/request"
    img = qrcode.make(request_url)
    img.save(config.QR_CODE_PATH)
    print(f"[qr] QR code saved to {config.QR_CODE_PATH} → {request_url}")


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
    return render_template(
        "admin.html",
        authenticated=authenticated,
        state=state,
    )


@app.route("/admin/skip", methods=["POST"])
def admin_skip():
    svc.skip_track(sp)
    return redirect(url_for("admin"))


@app.route("/admin/toggle_requests", methods=["POST"])
def admin_toggle_requests():
    with _state_lock:
        _state["guest_requests_enabled"] = not _state["guest_requests_enabled"]
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
        })


# ---------------------------------------------------------------------------
# Web routes — Guest request
# ---------------------------------------------------------------------------

@app.route("/request")
def guest_request():
    with _state_lock:
        enabled = _state["guest_requests_enabled"]
    return render_template("request.html", enabled=enabled, results=[], query="")


@app.route("/request/search")
def guest_search():
    with _state_lock:
        enabled = _state["guest_requests_enabled"]
    if not enabled:
        return render_template("request.html", enabled=False, results=[], query="")

    query = request.args.get("q", "").strip()
    results = svc.search_tracks(sp, query) if query else []
    return render_template("request.html", enabled=True, results=results, query=query)


@app.route("/request/submit", methods=["POST"])
def guest_submit():
    with _state_lock:
        enabled = _state["guest_requests_enabled"]
    if not enabled:
        return redirect(url_for("guest_request"))

    track_uri = request.form.get("uri", "").strip()
    track_title = request.form.get("title", "Unknown")
    track_artist = request.form.get("artist", "")

    if not track_uri:
        return redirect(url_for("guest_request"))

    # Add to Spotify queue or playlist
    if config.SONG_REQUEST_PLAYLIST_ID:
        svc.add_track_to_playlist(sp, config.SONG_REQUEST_PLAYLIST_ID, track_uri)
    else:
        svc.add_track_to_queue(sp, track_uri)

    with _state_lock:
        _state["request_queue"].append({
            "title": track_title,
            "artist": track_artist,
            "uri": track_uri,
        })

    return render_template("submitted.html", title=track_title, artist=track_artist)


# ---------------------------------------------------------------------------
# Display loop
# ---------------------------------------------------------------------------

def display_loop():
    last_track_id = None

    while True:
        try:
            authenticated = svc.is_authenticated(sp)
            print(f"[display] authenticated={authenticated}")

            if authenticated:
                track = svc.get_current_track(sp)
                print(f"[display] track={track}")

                with _state_lock:
                    _state["current_track"] = track

                # Use track id + playing state as the key so pausing/resuming also refreshes
                current_id = (track["id"], track.get("is_playing")) if track else None

                if current_id != last_track_id:
                    if track:
                        print(f"[display] Showing: {track['title']} — {track['artist']} (playing={track.get('is_playing')})")
                        image = display_svc.build_display_image(track)
                    else:
                        print("[display] Nothing playing — showing idle screen.")
                        image = display_svc.build_idle_image()

                    eink.display(image)
                    last_track_id = current_id

        except Exception as e:
            print(f"[display] Error in display loop: {e}")

        time.sleep(config.DISPLAY_REFRESH_INTERVAL)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    generate_qr_code()

    display_thread = threading.Thread(target=display_loop, daemon=True)
    display_thread.start()

    print(f"[web] Starting Flask on {config.FLASK_HOST}:{config.FLASK_PORT}")
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=config.FLASK_DEBUG, use_reloader=False)
