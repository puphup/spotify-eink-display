import spotipy
from spotipy.oauth2 import SpotifyOAuth
import config


def get_spotify_client() -> spotipy.Spotify:
    auth_manager = SpotifyOAuth(
        client_id=config.SPOTIFY_CLIENT_ID,
        client_secret=config.SPOTIFY_CLIENT_SECRET,
        redirect_uri=config.SPOTIFY_REDIRECT_URI,
        scope=config.SPOTIFY_SCOPES,
        cache_path=config.SPOTIFY_CACHE_PATH,
        open_browser=False,
    )
    return spotipy.Spotify(auth_manager=auth_manager)


def get_current_track(sp: spotipy.Spotify) -> dict | None:
    """
    Returns a dict with track info, or None if nothing is playing.

    {
        "id": str,
        "title": str,
        "artist": str,
        "album": str,
        "album_art_url": str,
        "is_playing": bool,
        "progress_ms": int,
        "duration_ms": int,
    }
    """
    try:
        result = sp.current_playback()
    except Exception:
        return None

    if not result or not result.get("item"):
        return None

    item = result["item"]
    artists = ", ".join(a["name"] for a in item["artists"])
    images = item["album"]["images"]
    album_art_url = images[0]["url"] if images else None

    return {
        "id": item["id"],
        "title": item["name"],
        "artist": artists,
        "album": item["album"]["name"],
        "album_art_url": album_art_url,
        "is_playing": result.get("is_playing", False),
        "progress_ms": result.get("progress_ms", 0),
        "duration_ms": item.get("duration_ms", 0),
    }


def search_tracks(sp: spotipy.Spotify, query: str, limit: int = 10) -> list[dict]:
    """Search Spotify and return a list of track results."""
    try:
        results = sp.search(q=query, type="track", limit=limit)
    except Exception:
        return []

    tracks = []
    for item in results["tracks"]["items"]:
        artists = ", ".join(a["name"] for a in item["artists"])
        images = item["album"]["images"]
        tracks.append({
            "id": item["id"],
            "uri": item["uri"],
            "title": item["name"],
            "artist": artists,
            "album": item["album"]["name"],
            "album_art_url": images[0]["url"] if images else None,
        })
    return tracks


def add_track_to_queue(sp: spotipy.Spotify, track_uri: str) -> bool:
    """Add a track to the active playback queue."""
    try:
        sp.add_to_queue(track_uri)
        return True
    except Exception:
        return False


def add_track_to_playlist(sp: spotipy.Spotify, playlist_id: str, track_uri: str) -> bool:
    """Add a track to a specific playlist."""
    try:
        sp.playlist_add_items(playlist_id, [track_uri])
        return True
    except Exception:
        return False


def ensure_collaborative_playlist(sp: spotipy.Spotify, name: str, cache_path: str) -> dict:
    """
    Load the collaborative playlist from cache, verify it still exists,
    or create a new one. Returns {"id": str, "url": str}.
    """
    import json, os

    if os.path.exists(cache_path):
        with open(cache_path) as f:
            data = json.load(f)
        try:
            sp.playlist(data["id"], fields="id")  # verify it exists
            return data
        except Exception:
            pass  # playlist was deleted — create a new one

    user = sp.me()
    playlist = sp.user_playlist_create(
        user["id"],
        name,
        public=False,       # collaborative playlists must be private
        collaborative=True,
        description="Scan the QR code to add songs to this café playlist!",
    )
    data = {
        "id": playlist["id"],
        "url": playlist["external_urls"]["spotify"],
    }
    with open(cache_path, "w") as f:
        json.dump(data, f)
    print(f"[playlist] Created collaborative playlist: {data['url']}")
    return data


def skip_track(sp: spotipy.Spotify) -> bool:
    try:
        sp.next_track()
        return True
    except Exception:
        return False


def get_auth_url(sp: spotipy.Spotify) -> str:
    return sp.auth_manager.get_authorize_url()


def handle_callback(sp: spotipy.Spotify, code: str) -> bool:
    try:
        sp.auth_manager.get_access_token(code)
        return True
    except Exception:
        return False


def is_authenticated(sp: spotipy.Spotify) -> bool:
    try:
        token = sp.auth_manager.get_cached_token()
        return token is not None and not sp.auth_manager.is_token_expired(token)
    except Exception:
        return False
