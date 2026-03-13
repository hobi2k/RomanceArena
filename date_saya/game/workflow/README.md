# RomanceArena Asset Restyle Workflows

This folder contains workflows and presets for restyling assets in `game/images` to better match the look of `images/saya_neutral02.png`.

Current targets:

- character sprite to illustration
- main menu key visual
- vn cg scene from sprite + background
- vn cg scene from sprite + prompt
- backgrounds
- UI panels
- UI buttons
- UI icons

## Asset split

Do not process all assets with one workflow.

Use separate handling for:

- backgrounds such as `bg room.png`, `bg home.png`, `bg park.png`, `bg shop.png`, `bg map.png`
- large UI frames such as `UI menu base.png`, `UI home base.png`, `UI shop base.png`, `UI map base.png`, `UI mirror base.png`
- small UI controls such as buttons, gift icons, labels, and hover states

## Included files

- `romancearena_background_style_transfer_ipadapter.json`
- `romancearena_character_illustration_from_sprite.json`
- `romancearena_character_illustration_single_source.json`
- `romancearena_main_menu_saya_keyvisual.json`
- `romancearena_vn_cg_from_sprite_and_background.json`
- `romancearena_vn_cg_from_sprite_prompt_only.json`
- `ui_restyle_guide.md`
- `character_illustration_prompt_preset.txt`
- `main_menu_prompt_preset.txt`
- `vn_cg_prompt_preset.txt`
- `ui_prompt_preset.txt`
- `romancearena_sprite_style_transfer_ipadapter.json`

## Recommended approach

### Character sprite to illustration

Use the character illustration workflow when you want to turn a standing game sprite into a more polished promo-style illustration while keeping the original pose, outfit, and expression family.

- source image: one character sprite such as `saya_neutral01.png`
- style reference: `images/saya_neutral02.png`
- method: `img2img + IPAdapter style transfer`

Use this for:

- higher-detail splash art
- gallery illustration variants
- marketing or key art drafts based on in-game sprites

Do not use it for direct UI replacement.

If your goal is stricter than that, and you want:

- the in-game sprite itself to define the character identity
- no separate style reference image
- a more direct `sprite -> illustration` conversion

use `romancearena_character_illustration_single_source.json`.

That workflow has:

- one character sprite input only
- no second image loader
- stronger prompt guidance toward a finished illustration
- lower risk of identity drift caused by a mismatched reference image

### Main Menu Key Visual

Use `romancearena_main_menu_saya_keyvisual.json` for the title screen shot where Saya appears enlarged on the right side of the frame.

- input A: `saya_neutral02.png` used as the `IPAdapter Plus` character reference
- input B: a 1280x720 menu background or `UI menu base.png` used as the layout base
- output: one main-menu-ready key visual draft

Composition target:

- character occupies the right half to right third of the image
- left side stays relatively open for logo and menu buttons
- overall lighting and polish should feel like a title screen, not an in-game sprite

### VN CG from sprite and background

Use `romancearena_vn_cg_from_sprite_and_background.json` when you already know the scene background and want the sprite turned into a full CG-like shot inside that space.

- input A: character sprite used as the `IPAdapter Plus` character reference
- input B: background image used as the scene latent / composition base
- output: one scene illustration / CG draft

This is the more controllable workflow for:

- room scenes
- date scenes
- event CG mockups

Recommended use:

1. choose the target background
2. describe the scene mood in the positive prompt
3. keep denoise moderate so the background layout stays stable

This workflow now includes a second low-denoise refine pass so the first draft can be cleaned up into a more unified CG image.

### VN CG from sprite and prompt

Use `romancearena_vn_cg_from_sprite_prompt_only.json` when you do not have a finished background and want the model to create the scene around the character.

- input: character sprite used as the `IPAdapter Plus` character reference
- output: one scene illustration / CG draft with generated background

This is better for:

- brainstorming event scenes
- rough ideation for story moments
- testing new date or route CG concepts

This version is less stable than the background-guided workflow, so expect more iteration.

In this workflow the scene starts from `EmptyLatentImage`, not from the sprite itself, so the prompt matters much more.

### Backgrounds

Use the background ComfyUI workflow:

- source image: one existing background
- style reference: `images/saya_neutral02.png`
- method: `img2img + IPAdapter style transfer`

This works because backgrounds can tolerate painterly reinterpretation as long as the room layout and major objects stay readable.

### UI

Do not use the background workflow directly on small UI elements.

For UI, use AI only for broad visual direction:

- soften gradients
- harmonize palette toward Saya's cool dark tones
- add subtle painted highlights
- reduce harsh synthetic gloss

For game-ready UI, preserve:

- exact silhouette
- exact size
- exact text placement
- idle/hover/locked consistency

That means the safe pipeline is:

1. Generate 1 to 3 style studies on large UI base panels only.
2. Pick one direction.
3. Rebuild button/icon states from that direction with manual paintover or editor-side batch color treatment.

## Required ComfyUI components

Base nodes:

- `CheckpointLoaderSimple`
- `LoadImage`
- `CLIPTextEncode`
- `VAEEncode`
- `KSampler`
- `VAEDecode`
- `SaveImage`

Custom nodes / models:

- `ComfyUI_IPAdapter_plus`
- one anime-friendly SDXL checkpoint
- one SDXL-compatible IPAdapter model
- one CLIP vision model supported by your IPAdapter install

## Background starting settings

- steps: `30`
- CFG: `5.0`
- sampler: `dpmpp_2m_sde`
- scheduler: `karras`
- denoise: `0.48`
- IPAdapter weight: `0.70`

Adjustment guide:

- If layout drifts too much, lower denoise to `0.35 - 0.42`.
- If style shift is too weak, raise denoise to `0.52 - 0.58`.
- If the image becomes too character-like or over-stylized, lower IPAdapter weight to `0.55 - 0.65`.

## Character illustration starting settings

- steps: `32`
- CFG: `5.8`
- sampler: `dpmpp_2m_sde`
- scheduler: `karras`
- denoise: `0.50`
- IPAdapter weight: `0.74`

Adjustment guide:

- If facial identity drifts, lower denoise to `0.38 - 0.45`.
- If the image still looks too much like a flat sprite, raise denoise to `0.55 - 0.62`.
- If the pose starts changing, lower both denoise and IPAdapter weight slightly.

## VN CG starting settings

Sprite + background:

- steps: `32`
- CFG: `5.6`
- denoise: `0.46`

Sprite + prompt only:

- steps: `34`
- CFG: `6.0`
- denoise: `0.58`

Adjustment guide:

- If the character disconnects from the scene, lower denoise slightly.
- If the output still looks like a pasted sprite, raise denoise slightly.
- If background-guided composition drifts, simplify the scene prompt and reduce CFG.

## Main menu starting settings

- steps: `34`
- CFG: `5.8`
- first pass denoise: `0.44`
- second pass denoise: `0.18`
- IPAdapter weight: `0.88`

## Practical warnings

- Small UI buttons will blur easily under generative redraw.
- Text-bearing assets should not be regenerated unless you plan to redraw the text layer manually.
- Hover/idle/locked button states should share the same post-process recipe, not independent generations.
- Keep originals untouched and export restyled variants into a separate folder first.
- Transparent sprite input is fine, but generated illustration output may need alpha cleanup if you want a transparent final asset.
