default llm_base_url = "http://127.0.0.1:8010"
default llm_session_id = ""
default llm_last_options = []
default llm_last_emotion = "neutral"
default llm_last_wav = ""

init python:
    import json
    import uuid
    import urllib.request
    import urllib.error
    import socket

    HTTP_TIMEOUT_SEC = 120

    def _llm_post(path, payload):
        url = store.llm_base_url.rstrip("/") + path
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        last_err = None
        for _ in range(2):
            try:
                with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SEC) as resp:
                    body = resp.read().decode("utf-8")
                    return json.loads(body)
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, socket.timeout) as e:
                last_err = e
        raise last_err

    def llm_start_if_needed():
        if store.llm_session_id:
            return True
        sid = "renpy-" + uuid.uuid4().hex[:8]
        try:
            _llm_post("/start", {"session_id": sid, "npc_id": "saya"})
            store.llm_session_id = sid
            return True
        except Exception:
            return False

    def llm_turn(player_action, player_text):
        if not llm_start_if_needed():
            return None
        try:
            data = _llm_post(
                "/turn",
                {
                    "session_id": store.llm_session_id,
                    "player_action": str(player_action),
                    "player_text": str(player_text),
                    "player_name": str(getattr(store, "pName", "플레이어")),
                },
            )
            store.llm_last_options = list(data.get("player_options", []))
            store.llm_last_emotion = str(data.get("emotion", "neutral"))
            store.llm_last_wav = str(data.get("wav_path") or "")
            return data
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
            return None
