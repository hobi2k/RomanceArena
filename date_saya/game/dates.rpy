# if you have multiple love interests then dateA can be either duplicated or have conditionals added, but you must have only one each of the other labels.
    
label dateA:
    scene bg room
    show neutral_saya
    "사야와의 데이트 세션이 시작됐다."
    $ renpy.show_screen("date")
    $ renpy.pause ()
    
    
label datetalk:
    $ renpy.hide_screen("date")
    
    if (curdate == "Saya"):
        if (talkcount > 0):
            $ talkcount -= 1
            $ rand = renpy.random.randint(1, 3)
            
            if (rand == 1):
                c "오늘은 연결 상태가 아주 좋아. 방 안 분위기도 딱 좋아."
            elif (rand == 2):
                c "디지털 아카이브에서 같이 볼 영상 몇 개 골라뒀어. 취향 맞을 거야."
            else:
                c "오늘 아바타 스타일 어때? 너 반응이 궁금했어."
            $ mood += 1
            
        else:
            c "Hey, I'm getting kind of bored. Can we do something else?"
        jump dateA
        
        
label dategift:
    $ renpy.hide_screen("giftdate")
    
    if (giftcount > 0):
        $ globals()[curgift] -= 1
        $ mood += 1
        $ giftcount -= 1
        
        if (curdate == "Saya"):
            c "Oh! Thank you, [pName], this is great!"
            jump dateA
            
    else:
        if (curdate == "Saya"):
            c "Hey, I'm getting kind of bored. Can we do something else?"
            jump dateA
            
            
label datephoto:
    $ renpy.hide_screen("date")
    
    if (photocount > 0):
        $ photocount -= 1
        $ mood += 1
        show whiteflash
        
        if (curdate == "Saya"):
            c "Hee hee. This'll make a great memory, don't you think?"
            jump dateA
            
    else:
        if (curdate == "Saya"):
            c "Hey, I'm getting kind of bored. Can we do something else?"
            jump dateA
            
            
label datekiss:
    $ renpy.hide_screen("date")
    
    if (curdate == "Saya"):
        show whiteflash
        "*MWAH!*"
        $ Alove += 60
        if (Ad8 == False):
            $ Ad8 = True
            $ d8total -= 1
        c "오늘 정말 좋았어... 초대해줘서 고마워."
        c "다음 접속 때도 꼭 만나자."
        show loveupbig
        "데이트 성공! 관계도가 상승했다."
        jump parkA
        
        
label dateexit:
    $ renpy.hide_screen("date")
        
    if (curdate == "Saya"):
        c "벌써 나가려고? 괜찮아, 다음 접속 때 이어서 하자."
        jump parkA
