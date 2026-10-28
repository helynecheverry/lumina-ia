"""Offline Spanish prompting, conflict handling, and complete CLIP context encoding."""
import gc
import re
from functools import lru_cache
from pathlib import Path

from app.style_catalog import PRESETS, RECIPE_VERSION
from app.character_types import character_profile
from app.transformation_intent import resolve_character
from app.appearance import CONTROLS, validate_appearance

TRANSLATOR = Path(__file__).resolve().parents[1] / 'weights/influencer/translator'
TRANSLATION_TERMS = {
    r'\bajolotes?\b': 'axolotl',
    r'\bornitorrincos?\b': 'platypus',
    r'\bmantarrayas?\b': 'manta ray',
    r'\bmantis religiosa\b': 'praying mantis',
}


def protect_translation_terms(text):
    for pattern, english in TRANSLATION_TERMS.items():
        text = re.sub(pattern, english, text, flags=re.I)
    return text


def normalize_translation_terms(original, translated):
    if re.search(r'\bbranquias\s+externas\b', original, re.I):
        translated = re.sub(r'\b(?:outer|outsole|external)\s+gills\b', 'external gills', translated, flags=re.I)
    return translated


SPANISH = re.compile(r'[áéíóúñ¿¡]|\b(con|sin|chaqueta|camisa|sombrero|pelo|cabello|roja|rojo|azul|verde|negro|blanco|vestido|fondo|quiero|ponme|hazme|transformame|convertirme|convierteme|en|el|la|los|las|del|mi|soy|como|personaje|persona|rey|reina|flores|ojos|sonrisa|lleva|una|un|llevar|playa|ciudad|bosque|gafas|capa|dorado|rosa|morada|amarillo)\b', re.I)
CLOTHES = re.compile(r'\b(jacket|shirt|coat|dress|suit|outfit|wearing|hoodie|blazer|sweater|armor|cape|clothing|t-shirt)\b', re.I)


@lru_cache(maxsize=32)
def translate_prompt(text):
    text = text.strip()
    if not text:
        return '', 'none'
    english = re.search(r'\b(red|blue|green|white|black|yellow|pink|jacket|background|wearing|with|woman|man|portrait|photo|cinematic|lighting|forest|studio|golden|hour|light|watercolor|oil|clay|human|hybrid|humanoid|snake|wolf|tiger|fox|scales|robot|transform)\b', text, re.I)
    if not SPANISH.search(text) and english:
        return text, 'en'
    if not (TRANSLATOR / 'pytorch_model.bin').is_file():
        raise ValueError('Falta el traductor local de español. Ejecuta scripts/download_creative_models.py.')
    import torch
    from transformers import MarianMTModel, MarianTokenizer
    tokenizer = MarianTokenizer.from_pretrained(TRANSLATOR, local_files_only=True)
    model = MarianMTModel.from_pretrained(TRANSLATOR, local_files_only=True, low_cpu_mem_usage=True)
    try:
        torch.set_num_threads(2)
        inputs = tokenizer(protect_translation_terms(text), return_tensors='pt', truncation=False)
        if inputs.input_ids.shape[-1] > 256:
            raise ValueError('La descripción es demasiado larga para el traductor')
        with torch.inference_mode():
            tokens = model.generate(**inputs, max_new_tokens=192, num_beams=4)
        return normalize_translation_terms(text, tokenizer.decode(tokens[0], skip_special_tokens=True)), 'es'
    finally:
        del model, tokenizer
        gc.collect()


def compile_prompt(preset, text='', translated=None, character_type='natural', appearance=None, inspiration_id=''):
    recipe = PRESETS[preset]
    english, language = translate_prompt(text) if translated is None else (translated, 'provided')
    if inspiration_id:
        from app.discovery_catalog import inspiration_profile
        profile, intent = inspiration_profile(character_type,inspiration_id,text,english)
    else:
        profile, intent = resolve_character(character_type, text, english)
    backbone = profile.get('backbone') or recipe['backbone']
    description = (text+' '+english).lower()
    composition = 'full_body' if re.search(r'cuerpo (?:completo|entero)|pies a cabeza|full[- ]body|head[- ]to[- ]toe',description) else ('closeup' if re.search(r'primer plano|close[- ]?up',description) else 'portrait')
    appearance = validate_appearance(appearance)
    expressions = {'presentation':r'\b(woman|man|feminine|masculine|androgynous)\b',
                   'outfit':CLOTHES.pattern,
                   'scene':r'\b(background|backdrop|beach|forest|city|spaceship|kitchen|library)\b',
                   'lighting':r'\b(light|lighting|sunlight|daylight|exposure)\b'}
    ignored = [key for key in appearance if re.search(expressions[key], english, re.I)]
    selected = {key:CONTROLS[key]['options'][value][1] for key,value in appearance.items() if key not in ignored}
    if ('anthropomorphic' in profile.get('subject','') or character_type == 'alien') and 'presentation' in selected:
        selected['presentation'] = selected['presentation'].replace(', man','').replace(', woman','')
    # Put the user's direction first and suppress conflicting default clothing.
    character_parts = [profile['direction']]
    parts = [english.strip().rstrip('.'), *selected.values(), *character_parts]
    if profile['hair'] and not re.search(r'\b(hair|hairstyle|haircut|bald)\b', english, re.I):
        parts.append(profile['hair'])
        character_parts.append(profile['hair'])
    if profile['accessory'] and not re.search(r'\b(glasses|eyeglasses|spectacles)\b', english, re.I):
        parts.append(profile['accessory'])
        character_parts.append(profile['accessory'])
    clauses = recipe['prompt'].split(', ')
    if 'scene' in selected or re.search(expressions['scene'], english, re.I):
        clauses = [item for item in clauses if not re.search(r'background|backdrop|forest|beach|city|Tokyo|planet|ship|ocean|library|palace|throne|kitchen|mountains|landscape|restaurant|cafe|coral',item,re.I)]
    if 'lighting' in selected or re.search(expressions['lighting'], english, re.I):
        clauses = [item for item in clauses if not re.search(r'light|sunset|glow|exposure',item,re.I)]
    if composition == 'full_body':
        clauses = [re.sub(r'portrait', 'full body scene', item, flags=re.I) for item in clauses]
    parts.append(', '.join(clauses))
    if not intent['custom_character'] and not CLOTHES.search(english) and 'outfit' not in selected:
        parts.append(recipe['outfit'])
    parts.append(('full body view of ' if composition == 'full_body' else 'portrait of ') + profile.get('subject', 'one person') + ', detailed face, expressive eyes')
    if backbone == 'photo':
        parts.append(('detailed requested skin textures' if intent['custom_character'] else 'natural skin texture') + ', professional photography, balanced exposure')
    negative = 'low quality, blurry, deformed, bad anatomy, duplicate person, watermark, text, plastic skin, malformed eyes, oversharpened'
    negative += ', ' + profile['negative']
    if backbone == 'art':
        negative += ', photograph, photographic, camera photo'
    return {'original_prompt':text, 'translated_prompt':english, 'prompt_language':language,
            'effective_prompt':', '.join(part for part in parts if part), 'negative_prompt':negative,
            'recipe_version':RECIPE_VERSION, 'backbone':backbone,
            'character_type':character_type, 'character_label':profile['label'],
            'appearance':appearance, 'ignored_selections':ignored,
            'identity_mode':profile['identity_mode'], 'character_version':profile['character_version'],
            'character_direction':', '.join(character_parts),
            'composition':composition, 'style_direction':', '.join(clauses),
            'appearance_direction':', '.join(selected.values()),
            'reference_context':profile['reference_context'],
            'identity_min':profile.get('min_identity',.3), 'identity_max':profile.get('max_identity',1.2),
            **intent}


def encode_complete_prompt(pipe, positive, negative):
    """Encode all 75-token chunks; never silently discard the user's instructions."""
    import torch
    tokenizer = pipe.tokenizer
    size = tokenizer.model_max_length - 2
    def chunks(text):
        tokens = tokenizer(text, add_special_tokens=False, truncation=False).input_ids
        return [tokens[i:i+size] for i in range(0,len(tokens),size)] or [[]]
    pos, neg = chunks(positive), chunks(negative)
    count = max(len(pos), len(neg))
    if count > 4:
        raise ValueError('Reduce la descripción: supera el contexto admitido')
    def encode(parts):
        encoded = []
        for index in range(count):
            content = parts[index] if index < len(parts) else []
            sequence = [tokenizer.bos_token_id] + content + [tokenizer.eos_token_id]
            sequence += [tokenizer.pad_token_id] * (tokenizer.model_max_length - len(sequence))
            ids = torch.tensor([sequence], device=pipe._execution_device)
            encoded.append(pipe.text_encoder(ids)[0])
        return torch.cat(encoded, dim=1)
    return encode(pos), encode(neg), count


def character_detail_text(english, kind):
    """Keep requested details while replacing ambiguous whole-animal commands."""
    if kind == 'freeform':
        return english.strip().rstrip('.')
    animal = {'robot': r'(?:robot|cyborg)', 'cat': r'(?:cat|feline)', 'snake': r'(?:snake|serpent)'}.get(kind, re.escape(kind))
    command = r'(?:(?:I (?:want|would like) to (?:generate|create|become)|(?:turn|transform|convert) me into|make me(?: into)?)\s+)?'
    target = r'(?:an?\s+)?(?:human[- ]+)?'+animal+r'(?:[- ]+(?:human|hybrid))?\b'
    details = re.sub(r'^'+command+target, '', english.strip(), count=1, flags=re.I).strip(' ,.')
    return re.sub(r'^(?:with|having|featuring)\s+', '', details, flags=re.I)


def expand_visual_terms(text):
    return re.sub(r'\bexternal gills\b', 'feathery branching external gills with fine filament-like branches', text, flags=re.I)


def compile_studio_prompt(preset, text='', character_type='natural', model_id='portrait_sd15', framing='square', appearance=None, inspiration_id='', target_age=None):
    from app.model_registry import validate_selection
    size = validate_selection(model_id, framing)
    if target_age is not None:
        from app.youth import youth_recipe
        return youth_recipe(target_age, model_id, framing, size)
    recipe = compile_prompt(preset, text, character_type=character_type, appearance=appearance, inspiration_id=inspiration_id)
    if framing == 'portrait' and recipe['composition'] == 'portrait':
        recipe['effective_prompt'] += ', vertical upper body portrait, complete hairstyle visible, carefully composed head and shoulders'
    if model_id in ('flux_klein', 'qwen_edit'):
        if recipe['custom_character']:
            if inspiration_id:
                from app.discovery_catalog import inspiration_profile
                profile, _ = inspiration_profile(character_type,inspiration_id,text,recipe['translated_prompt'])
            else:
                profile, _ = resolve_character(character_type, text, recipe['translated_prompt'])
            key = recipe['resolved_character_type']
            intense = recipe['transformation_intensity'] == 'strong'
            parts = (['Create an intense humanoid creature whose human mouth shape and recognizable expression come from the reference person. Make the requested creature traits pronounced and unmistakable, transforming the skin, eye anatomy and outer facial silhouette.'] if intense else ["Edit the reference person's appearance, keeping their human face shape and recognizable features."])
            english = recipe['translated_prompt']
            if inspiration_id:
                from app.discovery_catalog import get_inspiration
                target = get_inspiration(inspiration_id)
                parts = ["Edit this exact reference person's portrait into an intense humanoid creature. Preserve their underlying facial proportions, eye spacing, nose bridge, human lips and characteristic expression so the person remains recognizable. Transform the skin texture and color, ears, eyes and body with pronounced creature traits."] if intense else parts
                automatic = 'Conviérteme en una criatura humanoide inspirada en '+target['name']+', conservando algunos rasgos de mi foto.'
                # Named cartoon archetypes otherwise overpower the supplied face.
                # The explicit visual profile carries the target; retain custom details.
                english = '' if text.strip()==automatic else re.sub(re.escape(target['name']), 'this creature', english, flags=re.I)
                recipe['inspiration_recipe_version'] = '1.1'
            if not intense and not re.search(r'\b(hair|hairstyle|bald)\b', english, re.I):
                parts.append('Keep their original hairstyle.')
            if key in ('fox','cat','wolf','tiger') and recipe['transformation_intensity'] != 'strong' and not re.search(r'full face|entire face|whole face',english,re.I):
                parts.append('The center of the forehead and the central face remain exposed human skin.')
            details = expand_visual_terms(character_detail_text(english,key))
            if details: parts.append('Apply these requested details: '+details+'.')
            recipe['expanded_user_details'] = details
            if key == 'snake': parts.append(profile['visual_features']+'.')
            elif key != 'freeform': parts.append('Their transformed appearance includes '+profile['visual_features']+'.')
            if intense:
                center = "Keep identifiable cues from the reference person's gaze, human lip shape and expression within the creature's transformed face."
            else:
                center = 'Keep the center of the face human, with the person recognizable through their facial landmarks and expression.'
                if not re.search(r'\b(nose|snout|muzzle|mouth|lips|beak)\b', recipe['translated_prompt'], re.I):
                    center += ' The original human nose, lips and chin remain human and recognizable.'
            parts.append(center)
            parts.append('Render the image as '+recipe['style_direction']+'.')
            if recipe['appearance_direction']: parts.append('Apply '+recipe['appearance_direction']+'.')
            if recipe['composition'] == 'full_body': parts.append('Show the entire body from head to feet, with enough space around the figure.')
            elif recipe['composition'] == 'closeup': parts.append('A close-up of the face with eyes in sharp focus.')
            elif framing == 'portrait': parts.append('Vertical composition showing the head and shoulders completely.')
            recipe['effective_prompt'] = ' '.join(parts)
            recipe.update(model_id=model_id, framing=framing, requested_size=size)
            return recipe
        identity_direction=('Preserve the identity and facial features of this exact person. '
                            'Keep the original human face shape, eyes, nose, lips and jawline recognizable. '
                            'Apply the requested character features as localized enhancements to that face. ')
        identity_direction += character_profile(character_type).get('edit_scope','')+' '
        recipe['effective_prompt'] = ('Transform the reference person into the requested portrait. '+identity_direction+
            'Change the outfit, lighting and background as requested: ' + recipe['effective_prompt'])
    recipe.update(model_id=model_id, framing=framing, requested_size=size)
    return recipe
