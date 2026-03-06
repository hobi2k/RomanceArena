# Define your characters here.
init:
    $ pName = "Alexis"
    
    define c = Character("사야")
    define m = Character("[pName]")
    

    
    ## you can use this custom layer and position to show mc's image on top of all text as well as during choices, or just ignore it and use a normal side image.
    #   show side mc onlayer mcsprite at midleft
    #   hide side mc onlayer mcsprite

label start:
    $ renpy.show_screen("nameinput")
    
label intro:
    # this populates the mini-gallery feature with images, if you don't intend to use it, just set "usegallery" to False.
    $ usegallery = True
    call makegal from _call_makegal
    
    
    scene bg map
    "현실 세계와 디지털 세계가 연결된 지 오래됐다."
    "당신은 현실의 집에서 접속해, 디지털 공간 속 사야의 방으로 향할 수 있다."
    "오늘도 사야와의 거리를 좁히기 위해 하루를 시작한다."
    
    
    # if you dont want the player to have a quick-button that takes them home or to the main map from wherever they are, set this to False instead.
    # if you do want that, leave it -- but make sure to toggle it off/on before and after cutscenes so the player cant accidentally teleport out of dialogue.
    $ canwarp = True
    
    # leave these!
    $ renpy.show_screen("statusbar")
    jump map
