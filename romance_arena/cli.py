from __future__ import annotations

from .engine import RomanceArenaEngine
from .models import Action
from .npc.configs import NPCS


def _choose_npc_id() -> str:
    print("=== NPC 선택 ===")
    for npc in NPCS.values():
        print(f"- {npc.npc_id}: {npc.name} | {npc.scenario}")
    while True:
        npc_id = input("npc_id 입력 (saya/mai): ").strip().lower()
        if npc_id in NPCS:
            return npc_id
        print("잘못된 npc_id입니다.")


def _choose_action(npc_id: str) -> Action:
    values = [a.value for a in NPCS[npc_id].player_actions]
    print("\n가능 행동:", ", ".join(values))
    while True:
        raw = input("player_action 입력: ").strip().lower()
        try:
            action = Action(raw)
            if action not in NPCS[npc_id].player_actions:
                print("해당 NPC 시나리오에서 허용되지 않은 action입니다.")
                continue
            return action
        except ValueError:
            print("유효하지 않은 action입니다.")


def main() -> None:
    npc_id = _choose_npc_id()
    engine = RomanceArenaEngine(NPCS[npc_id], session_id=f"cli-{npc_id}")
    print(f"\n세션 시작: {NPCS[npc_id].name} ({npc_id})")

    while True:
        action = _choose_action(npc_id)
        result = engine.step(action)
        s = result.state
        print(f"\n[PLAYER TURN]\n{result.player_turn_text}")
        print(f"\n[NPC TURN]\n{result.npc_turn_text}")
        print(f"[NPC action] {result.npc_action.value}")
        print(
            f"[STATE] affection={s.affection}, trust={s.trust}, interest={s.interest}, "
            f"jealousy={s.jealousy}, mood={s.mood}({s.mood_label}), stage={s.relationship_stage.value}"
        )
        print(f"[Outcome] {result.outcome}")

        if result.outcome != "ongoing":
            print("게임 종료")
            break

        if input("\n계속하려면 Enter, 종료하려면 q: ").strip().lower() == "q":
            break


if __name__ == "__main__":
    main()
