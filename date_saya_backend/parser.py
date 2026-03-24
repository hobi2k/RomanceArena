from __future__ import annotations

from dataclasses import dataclass
import re


def _strip_meta_prefix(text: str) -> str:
    """메타 접두어(서술/대사 등)를 제거한다.

    Args:
        text: 원본 텍스트.

    Returns:
        str: 메타 접두어가 제거된 텍스트.
    """
    t = (text or "").strip()
    if not t:
        return ""
    patterns = [
        r"^\s*(서술|대사|narration|dialogue)\s*[:：]\s*",
        r"^\s*\[\s*(서술|대사|narration|dialogue)\s*\]\s*",
    ]
    for p in patterns:
        t = re.sub(p, "", t, flags=re.IGNORECASE)
    return t.strip()


def _strip_meta_suffix(text: str) -> str:
    """메타 접미어(서술/대사 꼬리 라벨)를 제거한다.

    Args:
        text: 원본 텍스트.

    Returns:
        str: 메타 접미어가 제거된 텍스트.
    """
    t = (text or "").strip()
    if not t:
        return ""
    patterns = [
        r"\s*(서술|대사|narration|dialogue)\s*[:：]\s*$",
        r"\s*\[\s*(서술|대사|narration|dialogue)\s*\]\s*$",
    ]
    for p in patterns:
        t = re.sub(p, "", t, flags=re.IGNORECASE)
    return t.strip()


@dataclass
class RPBlock:
    """RP 파싱 결과 데이터 구조.

    Args:
        narration: 서술 블록 문자열.
        dialogue: 대사 블록 문자열.

    Returns:
        RPBlock: 파싱된 서술/대사 묶음.
    """
    narration: str
    dialogue: str


def parse_rp_output(text: str) -> RPBlock:
    """RP 출력 문자열을 서술/대사로 분리한다.

    Args:
        text: 모델이 생성한 원문 텍스트.

    Returns:
        RPBlock: 큰따옴표 대사를 추출한 결과.
    """
    text = (text or "").strip()
    if not text:
        return RPBlock(narration="", dialogue="")

    match = re.search(r'"([^"]+)"', text, flags=re.DOTALL)
    if match:
        dialogue = _strip_meta_suffix(_strip_meta_prefix(match.group(1).strip()))
        narration = (text[: match.start()] + text[match.end() :]).strip()
        narration = narration.replace("\n", " ").strip()
        narration = _strip_meta_suffix(_strip_meta_prefix(narration))
        return RPBlock(narration=narration, dialogue=dialogue)
    raise ValueError(f"invalid rp format (missing quoted dialogue): {text}")


def emotion_to_image_key(emotion: str) -> str:
    """감정 라벨을 Ren'Py 이미지 키로 변환한다.

    Args:
        emotion: 감정 라벨 문자열.

    Returns:
        str: 표정 스프라이트 키(`smile_saya` 등).
    """
    table = {
        "happy": "smile_saya",
        "sad": "crying_saya",
        "angry": "annoyed_saya",
        "neutral": "neutral_saya",
    }
    return table.get(emotion, "neutral_saya")
