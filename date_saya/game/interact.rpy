# each location is designed to hold one love interest, so "park" and "parkA" should be duplicated or edited to fit your own needs.

init python:
    def _show_saya_sprite(image_key):
        """사야 표정 스프라이트를 하나만 남기고 교체 표시한다."""
        renpy.hide("neutral_saya")
        renpy.hide("smile_saya")
        renpy.hide("crying_saya")
        renpy.hide("annoyed_saya")
        if image_key == "smile_saya":
            renpy.show("smile_saya")
        elif image_key == "crying_saya":
            renpy.show("crying_saya")
        elif image_key == "annoyed_saya":
            renpy.show("annoyed_saya")
        else:
            renpy.show("neutral_saya")
    
label park:
    $ renpy.hide_screen("townmap")
    $ renpy.hide_screen("maphome")
    $ renpy.hide_screen("mapshop")
    scene bg saya_room
    show neutral_saya
    "디지털 세계, 사야의 방에 접속했다."
    
    # this checks if youre at the end of the game (by default set to day 31), and sends you to the ending with the specified character.
    if (day > lastDay):
        $ renpy.hide_screen("townmap")
        "사야와의 엔딩으로 진행할까?"
        menu:
            "Yes":
                jump endA
            "No":
                jump map
    
    call relAcheck from _call_relAcheck
    jump parkA
    
    
# this is separate from park so that the relationship upgrade scene doesnt replay when it shouldnt.
label parkA:
    scene bg saya_room
    show neutral_saya
    
    # reset date tallies to default in case we end up going on one
    $ mood = 0
    $ talkcount = talkcountmax
    $ giftcount = giftcountmax
    $ photocount = photocountmax
    
    # these calculations determine the date variables. curbar uses the relationship status to determine progress to next date, assuming it takes 100 points to reach each stage.
    $ curdate = "Saya"
    $ currel = Arel
    
    if (currel == "Stranger"):
        $ curnext = pointsfriend
        $ curbar = min(Alove, pointsfriend)
    if (currel == "Friend"):
        $ curnext = pointslove - pointsfriend
        $ curbar = min(Alove - pointsfriend, pointslove - pointsfriend)
    if (currel == "Lover"):
        $ curnext = pointssoul - pointslove
        $ curbar = min(Alove - pointslove, pointssoul - pointslove)
    if (currel == "Soulmate"):
        $ curnext = 100
        $ curbar = 100
    
    $ renpy.show_screen("mapchat")
    $ renpy.pause ()
    
    
# a simple little label that will handle the relationship upgrades when youre close enough. each LI should have their own version of this label.
label relAcheck:
    $ canwarp = False
    $ renpy.hide_screen("townmap")
    if (Alove >= pointsfriend) and (Arel == "Stranger"):
        $ Arel = "Friend"
        
        # put your own dialogue here
        
        "사야와 이제 '친구' 관계가 되었다. 선물을 줄 수 있다."
        
    if (Alove >= pointslove) and (Arel == "Friend"):
        $ Arel = "Lover"
        
        # put your own dialogue here
        
        "사야와 연인 단계에 진입했다. 데이트를 진행할 수 있다."
        
    if (Alove >= pointssoul) and (Arel == "Lover"):
        $ Arel = "Soulmate"
        
        # put your own dialogue here
        
        "사야와 소울메이트가 되었다. 31일 이후 특별 엔딩을 볼 수 있다."
        
    $ canwarp = True
    return
    
    
# if you have multiple love interests you can add an "if (curdate == ??)" to this label too, but if you have a lot of potential dialogue itll likely be more efficient to put each character in a new label and use this to jump to the right one.
label chattalk:
    $ renpy.hide_screen("mapchat")
    $ canwarp = False
    if (HP >= 10):
        $ HP -= 10
        $ _resp = llm_turn("talk", "대화를 이어간다.")
        if _resp:
            $ _show_saya_sprite(_resp["image_key"])
            if _resp["saya_narration"]:
                "[_resp['saya_narration']]"
            c "[_resp['saya_dialogue']]"
            if _resp["wav_path"]:
                play sound _resp["wav_path"]

            if _resp["player_options"]:
                $ _o = _resp["player_options"]
                $ _chosen = None
                menu:
                    "[_o[0]]" if len(_o) > 0:
                        $ _chosen = _o[0]
                    "[_o[1]]" if len(_o) > 1:
                        $ _chosen = _o[1]
                    "[_o[2]]" if len(_o) > 2:
                        $ _chosen = _o[2]

                # 플레이어 선택지를 다음 턴의 실제 입력으로 전달해 대화를 이어간다.
                if _chosen:
                    $ _resp = llm_turn("talk", _chosen)
                    if _resp:
                        $ _show_saya_sprite(_resp["image_key"])
                        if _resp["saya_narration"]:
                            "[_resp['saya_narration']]"
                        c "[_resp['saya_dialogue']]"
                        if _resp["wav_path"]:
                            play sound _resp["wav_path"]
            $ Alove += 8
            show loveup
        else:
            c "지금은 연결이 불안정해. 잠깐 뒤에 다시 시도해줘."
    else:
        "You don't have enough HP for that!"
    $ canwarp = True
    jump parkA
    
    
label chatgift:
    $ renpy.hide_screen("chatgift")
    if (currel == "Stranger"):
        if (curdate == "Saya"):
            $ _resp = llm_turn("gift", "선물을 건넨다.")
            if _resp:
                $ _show_saya_sprite(_resp["image_key"])
                if _resp["saya_narration"]:
                    "[_resp['saya_narration']]"
                c "[_resp['saya_dialogue']]"
            else:
                c "음... 아직은 조금 조심스럽네."
            jump parkA
            
    else:
        $ globals()[curgift] -= 1
        
        if (curdate == "Saya"):
            $ _resp = llm_turn("gift", "선물을 건넨다.")
            if _resp:
                $ _show_saya_sprite(_resp["image_key"])
                if _resp["saya_narration"]:
                    "[_resp['saya_narration']]"
                c "[_resp['saya_dialogue']]"
                if _resp["wav_path"]:
                    play sound _resp["wav_path"]
            else:
                c "고마워, [pName]."
            $ Alove += 10
            show loveup
            jump parkA
    

label chatdate:
    $ renpy.hide_screen("mapchat")
    if (currel == "Stranger") or (currel == "Friend"):
        
        if (curdate == "Saya"):
            $ _resp = llm_turn("invite_date", "데이트를 제안한다.")
            if _resp:
                $ _show_saya_sprite(_resp["image_key"])
                if _resp["saya_narration"]:
                    "[_resp['saya_narration']]"
                c "[_resp['saya_dialogue']]"
            else:
                c "미안... 오늘은 좋은 타이밍이 아닌 것 같아."
            jump parkA
            
    else:
        if (HP >= 50):
            $ HP -= 50
            
            if (curdate == "Saya"):
                $ _resp = llm_turn("invite_date", "데이트를 제안한다.")
                if _resp:
                    $ _show_saya_sprite(_resp["image_key"])
                    if _resp["saya_narration"]:
                        "[_resp['saya_narration']]"
                    c "[_resp['saya_dialogue']]"
                else:
                    c "정말? 좋아. 그럼 출발하자."
                jump dateA
                
        else:
            "You don't have enough HP for that!"
            jump parkA
