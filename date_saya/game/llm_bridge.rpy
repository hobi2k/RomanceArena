default llm_base_url = "http://127.0.0.1:8010"
default llm_session_id = ""
default llm_session_saved = False
default llm_last_options = []
default llm_last_emotion = "neutral"
default llm_last_image_key = ""
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
            store.llm_session_saved = False
            return True
        except Exception:
            return False

    def llm_mark_saved():
        if not store.llm_session_id:
            return False
        try:
            _llm_post("/session/save", {"session_id": store.llm_session_id})
            store.llm_session_saved = True
            return True
        except Exception:
            return False

    def llm_discard_unsaved_session():
        if not store.llm_session_id:
            return False
        if store.llm_session_saved:
            return True
        try:
            _llm_post("/session/discard", {"session_id": store.llm_session_id})
            store.llm_session_id = ""
            store.llm_session_saved = False
            return True
        except Exception:
            return False

    def llm_new_game():
        llm_discard_unsaved_session()
        store.llm_session_id = ""
        store.llm_session_saved = False

    def _llm_save_json_callback(data):
        data["llm_session_id"] = store.llm_session_id
        data["llm_session_saved"] = bool(store.llm_session_saved)
        # 실제 저장 시점에 백엔드 세션을 saved로 마킹
        llm_mark_saved()

    def _llm_after_load_callback():
        # Ren'Py 저장 데이터에서 기본 store 변수는 자동 복원된다.
        # 로드 직후 타입/값 정규화만 수행한다.
        store.llm_session_id = str(getattr(store, "llm_session_id", "") or "")
        store.llm_session_saved = bool(getattr(store, "llm_session_saved", False))

    if hasattr(config, "save_json_callbacks"):
        config.save_json_callbacks.append(_llm_save_json_callback)
    if hasattr(config, "after_load_callbacks"):
        config.after_load_callbacks.append(_llm_after_load_callback)

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
                    "player_love": int(getattr(store, "Alove", 0)),
                    "player_rel": str(getattr(store, "Arel", "Stranger")),
                    "player_charm": int(getattr(store, "charm", 0)),
                    "player_intel": int(getattr(store, "intel", 0)),
                    "player_create": int(getattr(store, "create", 0)),
                },
            )
            store.llm_last_options = list(data.get("player_options", []))
            store.llm_last_emotion = str(data.get("emotion", "neutral"))
            store.llm_last_image_key = str(data.get("image_key", ""))
            store.llm_last_wav = str(data.get("wav_path") or "")
            return data
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
            return None
