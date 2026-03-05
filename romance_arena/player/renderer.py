from __future__ import annotations

from ..models import Action


def render_player_turn_fallback(action: Action) -> str:
    if action == Action.TALK:
        return "플레이어는 차분하게 대화를 이어가며 상대의 눈을 바라본다.\n\"오늘은 네 얘기를 더 듣고 싶어.\""
    if action == Action.COMPLIMENT:
        return "플레이어는 상대의 변화를 눈치채고 미소를 지었다.\n\"너 오늘 분위기 정말 좋다.\""
    if action == Action.GIFT:
        return "플레이어는 준비한 선물을 조심스럽게 내밀었다.\n\"부담은 갖지 말고, 네 생각이 나서 준비했어.\""
    if action == Action.INVITE_DATE:
        return "플레이어는 잠시 숨을 고른 뒤 조심스럽게 제안했다.\n\"이번 주말에 같이 나갈래?\""
    if action == Action.APOLOGIZE:
        return "플레이어는 표정을 누그러뜨리며 진심으로 사과했다.\n\"아까 말이 거칠었어. 미안해.\""
    if action == Action.JOKE:
        return "플레이어는 무거운 분위기를 풀기 위해 가볍게 웃었다.\n\"너무 진지했지? 조금 웃어보자.\""
    if action == Action.TEASE:
        return "플레이어는 장난기 어린 표정으로 상대의 반응을 살폈다.\n\"그런 표정이면 더 놀리고 싶어지는데?\""
    if action == Action.IGNORE:
        return "플레이어는 잠시 거리를 두며 시선을 피했다.\n\"지금은 조금 생각할 시간이 필요해.\""
    return "플레이어는 숨을 고르고 차분하게 말을 고르기 시작했다.\n\"천천히 얘기해보자.\""
