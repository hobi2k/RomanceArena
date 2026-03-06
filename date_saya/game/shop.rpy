# shop! if you need multiple shops, you can either duplicate these labels or add a variable to determine which information is shown. be sure to do the same for mapshop in custom_screens.
label shop:
    $ renpy.hide_screen("townmap")
    $ renpy.hide_screen("maphome")
    $ renpy.hide_screen("mapchat")
    scene bg shop
    "현실 세계의 상점이다. 디지털 세계로 가져갈 선물을 준비할 수 있다."
    $ renpy.show_screen("mapshop")
    $ renpy.pause ()

label shoptalk:
    $ renpy.hide_screen("mapshop")
    
    # 상점 대사(설정 반영).
    
    $ rand = renpy.random.randint(1, 3)
    if (rand == 1):
        "점원: 디지털 전송 포장까지 하시려면 추가 포인트가 들어요."
    elif (rand == 2):
        "점원: 사야에게 줄 선물이라면 취향 맞춤 태그를 붙여드릴까요?"
    else:
        "점원: 오늘도 디지털 세계 접속 전에 들르셨네요."
    jump shop
    
# workHP and workpay are set in the mapshop screen. if you want to have multiple jobs in one location, you should set them up there -- this label can be used for any/all.
label shopwork:
    if (HP >= workHP):
        $ HP -= workHP
        $ gold += workpay
    else:
        $ renpy.hide_screen("mapshop")
        "You don't have enough HP for that!"
    jump shop
    
# giftprice and curgift are set in the mapshop screen, and store the item you clicked on and its price.
label shopbuy:
    if (gold >= giftprice):
        $ gold -= giftprice
        $ globals()[curgift] += 1
    else:
        $ renpy.hide_screen("mapshop")
        "You can't afford that!"
    jump shop
