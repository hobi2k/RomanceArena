init: 
    ## CUSTOMISABLE VARIABLES
    # these are the point values the player needs to reach each relationship stage with a LI. if you dont plan to use relationship stages, you can ignore these or set "pointsfriend" to the maximum affection you can get.
    $ pointsfriend = 100
    $ pointslove = 200
    $ pointssoul = 300
    
    # these are date variables. to succeed on a date, you have to do at least as many activities as indicated in "maxmood". the variables in "count" are how many times you can do each activity. adjust these however you like. 
    $ maxmood = 5
    $ mood = 0
    $ talkcountmax = 3
    $ giftcountmax = 1
    $ photocountmax = 1
    $ talkcount = talkcountmax
    $ giftcount = giftcountmax
    $ photocount = photocountmax
    
    # turn this to False if you don't want to use the built-in mini-gallery (represented as date photos in your bedroom)
    $ usegallery = True
        
    # required mechanic variables such as HP, money, and day. you can set these to start at any number you want
    $ maxHP = 50
    $ HP = 50
    $ gold = 100
    $ day = 1
    $ lastDay = 30
    
    # these are the starting stats of the player. you dont need to use the same names for stats, but these variable names are used in screens and template logic. you should set a maximum the player can train it to here.
    $ charm = 0
    $ intel = 0
    $ create = 0
    $ maxcharm = 99
    $ maxintel = 99
    $ maxcreate = 99
    
    
    # love interest variables. Alove is the numerical value of affection (for character 'A')  Arel is the phase the relationship is in. 'pointsonly' is a True/False variable that determines which of the former shows in the stats menu.
    # each love interest should have their own version of Alove and Arel. duplicate them as many times as needed.
    $ Alove = 0
    $ Arel = "Stranger"
    $ pointsonly = False
    
    
    # these are all item variables, which increase when you make or buy an item.
    $ cookies = 0
    $ games = 0
    $ bouquets = 0
    $ teddies = 0
    
    
    ## NON-CUSTOMISABLE VARIABLES
    # these are all adaptable variables that hold temporary information used in the dates, shops, and other screens. leave these alone.
    $ curdate = "None"
    $ currel = "None"
    $ curnext = 0
    $ curbar = 0
    $ curgift = "None"
    $ giftprice = 0
    $ workHP = 0
    $ workpay = 0
        
    # this variable should be turned off during cutscenes, to prevent the user from jumping to another room during dialogue using the status window
    $ canwarp = True
    
    # used so that pixel art reads clear
    define config.nearest_neighbor = True
    
    # this adds an additional layer for the purpose of showing the characters sprite over dialogue without relying on side images. this is aesthetic, so not necessary.
    define config.layers = [ 'master', 'transient', 'say', 'mcsprite', 'screens', 'overlay']
    define config.say_layer = "say"
    
    # rolling back past screens can sometimes cause unexpected behaviour, so it's been disabled. You can re-enable it; it shouldn't be game-breaking, just annoying.
    define config.rollback_enabled = False


    image whiteflash:
        Solid("#fff")
        alpha 0.0
        linear 0.25 alpha 0.8
        linear 0.75 alpha 0.0
        
    image white:
        Solid("#fff")
        
    image loveupbig:
        "UI/UI love up big.png"
        xpos 1180
        ypos 480
        alpha 0.0
        linear 0.40 alpha 1.0
        pause 1.0
        linear 0.75 alpha 0.0
    
    image loveup:
        "UI/UI love up small.png"
        xpos 1180
        ypos 480
        alpha 0.0
        linear 0.40 alpha 1.0
        pause 0.6
        linear 0.75 alpha 0.0
        
    transform midleft:
        xalign 0.065 yalign 1.0

    transform saya_stage_pose:
        xanchor 0.5
        yanchor 1.0
        xalign 0.56
        yalign 1.18
        zoom 0.58

    image saya_annoyed01 = "saya_annoyed01.png"
    image saya_annoyed02 = "saya_annoyed02.png"
    image saya_neutral01 = "saya_neutral01.png"
    image saya_neutral02 = "saya_neutral02.png"
    image saya_sad01 = "saya_sad01.png"
    image saya_smile01 = "saya_smile01.png"
    image saya_smile02 = "saya_smile02.png"
    image saya_smile03 = "saya_smile03.png"

    image player_neutral = "player_neutral.png"
    image player_smile = "player_smile.png"
    image player_annoyed = "player_annoyed.png"
    image player_neutral_face = "player_neutral_face.png"
    image player_smile_face = "player_smile_face.png"
    image player_annoyed_face = "player_annoyed_face.png"
        

define gui.about = _p("""
    Date With Saya.
    현실 세계와 디지털 세계를 오가며 사야와 관계를 쌓는 시뮬레이션.
""")

define config.default_show_empty_window = False

# the following code just ensures that hiding the interface with the middle mouse button hides things on custom layers, too.
init python:
    new_keymap = renpy.Keymap(
        rollback = renpy.rollback,
        screenshot = _screenshot,
        toggle_fullscreen = renpy.toggle_fullscreen,
        toggle_afm = _keymap_toggle_afm,
        toggle_skip = _keymap_toggle_skipping,
        fast_skip = _fast_skip,
        game_menu = _invoke_game_menu,
        hide_windows = renpy.curried_call_in_new_context("hide_interface"),
        launch_editor = _launch_editor,
        reload_game = _reload_game,
        developer = _developer,
        quit = renpy.quit_event,
        iconify = renpy.iconify,
        help = _help,
        choose_renderer = renpy.curried_call_in_new_context("_choose_renderer"),
        console = _console.enter,
        profile_once = _profile_once,
        memory_profile = _memory_profile,
        self_voicing = Preference("self voicing", "toggle"),
        clipboard_voicing = Preference("clipboard voicing", "toggle"),
        debug_voicing = Preference("debug voicing", "toggle"),
        progress_screen = _progress_screen,
        )

    config.underlay = [ new_keymap ]

label hide_interface:

    if renpy.context()._menu:
        return

    if _windows_hidden:
        return

    python:
        _windows_hidden = True
        voice_sustain()
        renpy.hide_screen("say", "say")
        renpy.hide_screen("statusbar", "screens")
        ui.saybehavior(dismiss=['dismiss', 'hide_windows'])
        ui.interact(suppress_overlay=True, suppress_window=True)
        _windows_hidden = False

    return
