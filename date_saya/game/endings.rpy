# this label will check your relationship with the character attached to it, and then play one of three endings. adjust the logic however you like.
label endA:
    $ canwarp = False
    
    ## add any dialogue that should be seen regardless of your relationship with the character
    
    if (Arel == "Stranger"):
        
        ## add your "bad ending" dialogue here
        
        scene white with dissolve
        
        "사야 배드 엔딩. 이번엔 거리를 좁히지 못했다."
        "다음 회차에서는 더 전략적으로 접근해보자."
        
    elif (Arel != "Soulmate"):
        
        ## add your "neutral ending" dialogue here
        
        scene white with dissolve
        
        "사야 노멀 엔딩. 충분히 가까워졌지만 아직 결정적인 한 수가 부족했다."
        "다음 회차에서는 타이밍을 노려보자."
        
    else:
        
        ## add your "good ending" dialogue here
        
        scene white with dissolve
        
        "사야 굿 엔딩. 디지털 세계와 현실 세계를 넘나들며 마음을 연결했다."
        "축하해."

    $ MainMenu(confirm=False)()
    
label badend:
    $ canwarp = False
    $ renpy.hide_screen("maphome")
    scene white with dissolve
    
    "현실 세계에서만 시간을 보내다 연결이 끊어졌다."
    "최악의 엔딩."
    $ MainMenu(confirm=False)()
