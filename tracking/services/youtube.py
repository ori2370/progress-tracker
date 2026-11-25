import hashlib
import html
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache
from django.utils.dateparse import parse_duration

class YouTubeSearchError(Exception):
    pass

def format_video_duration(value):
    try:
        duration = parse_duration(value)
    except (ValueError, TypeError, OverflowError):
        return "Duration unavailable"

    if duration is None or duration.total_seconds() <= 0:
        return "Duration unavailable"

    seconds = int(duration.total_seconds())
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"

    return f"{minutes}:{seconds:02d}"


def get_video_durations(video_ids):
    if not video_ids:
        return {}

    parameters = urlencode({
        "part": "contentDetails",
        "id": ",".join(video_ids),
    })

    request = Request(
        f"https://www.googleapis.com/youtube/v3/videos?{parameters}",
        headers={
            "X-Goog-Api-Key": settings.YOUTUBE_API_KEY,
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=10) as response:
            payload = json.load(response)

        return {
            item["id"]: format_video_duration(
                item.get("contentDetails", {}).get("duration", "")
            )
            for item in payload.get("items", [])
        }
    except (
        URLError,
        TimeoutError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
    ):
        return {}

def search_exercise_videos(exercise_name):
    if not settings.YOUTUBE_API_KEY:
        raise YouTubeSearchError("Video search is not configured.")

    query = f"{exercise_name.strip()} gym exercise technique"
    query_hash = hashlib.sha256(query.encode()).hexdigest()
    cache_key = f"youtube-search:v3:{query_hash}"

    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    parameters = urlencode({
        "part": "snippet",
        "type": "video",
        "q": query,
        "maxResults": 5,
        "safeSearch": "strict",
    })

    request = Request(
        f"https://www.googleapis.com/youtube/v3/search?{parameters}",
        headers={
            "X-Goog-Api-Key": settings.YOUTUBE_API_KEY,
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=10) as response:
            payload = json.load(response)
    except HTTPError as error:
        if error.code in (403, 429):
            raise YouTubeSearchError(
                "YouTube search is unavailable or its quota was reached. "
                "You can still enter a video link manually."
            ) from None
        raise YouTubeSearchError(
            "YouTube search is temporarily unavailable."
        ) from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise YouTubeSearchError(
            "Could not reach YouTube. Please try again later."
        ) from None

    videos = []

    try:
        for item in payload.get("items", []):
            video_id = item.get("id", {}).get("videoId", "")

            if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
                continue

            snippet = item["snippet"]
            videos.append({
                "id": video_id,
                "title": html.unescape(snippet["title"]),
                "channel": html.unescape(snippet["channelTitle"]),
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "thumbnail": (
                    f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"
                ),
            })
    except (KeyError, TypeError, AttributeError):
        raise YouTubeSearchError(
            "YouTube returned an unexpected response."
        ) from None

    durations = get_video_durations([video["id"] for video in videos])

    for video in videos:
        video["duration"] = durations.get(
            video["id"],
            "Duration unavailable",
        )

    cache.set(cache_key, videos, timeout=3600)
    return videos