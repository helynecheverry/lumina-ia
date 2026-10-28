"""Explicit age-regression recipe; no inference of the subject's historical age."""
MIN_AGE = 8
MAX_AGE = 17


def validate_target_age(age):
    if age is not None and (isinstance(age, bool) or not isinstance(age, int) or not MIN_AGE <= age <= MAX_AGE):
        raise ValueError('Elige una edad entera entre 8 y 17 años.')
    return age


def youth_recipe(age, model_id, framing, size):
    validate_target_age(age)
    if model_id not in ('flux_klein', 'qwen_edit'):
        raise ValueError('Tu versión más joven necesita un motor de edición con foto de referencia: FLUX o Qwen.')
    instruction = (
        f'Edit the supplied photograph to depict the SAME person at approximately {age} years old. '
        'Use the reference face as the identity anchor. Preserve their distinctive eye shape and spacing, '
        'nose shape, mouth, skin tone, hair color and recognizable facial characteristics. '
        'Apply age-appropriate facial development: softer facial contours, youthful skin and age-appropriate '
        'cheek fullness and jaw development. Remove adult age lines and facial hair. '
        'Keep their expression, camera angle, background and lighting. '
        'Show one person in an ordinary fully clothed head-and-shoulders photographic portrait, '
        'wearing a simple crew-neck shirt. Natural skin texture, no makeup or glamour styling. '
        'Make a plausible younger likeness of the reference person, preserving individuality.'
    )
    return dict(original_prompt='', translated_prompt='', prompt_language='none',
                effective_prompt=instruction, negative_prompt='unrelated person, different identity, adult face, beard, wrinkles, glamour, makeup, duplicate person, deformed face, text, watermark',
                recipe_version='youth-1.0', youth_recipe_version='1.0', target_age=age,
                creation_mode='youth', character_type='natural', character_label=f'Tu versión a los {age} años',
                backbone='photo', appearance={}, ignored_selections=[], identity_mode='reference_age_regression',
                character_version='youth-1.0', character_direction=instruction, composition='portrait',
                style_direction='natural photographic portrait', appearance_direction='', reference_context=1.1,
                identity_min=.8, identity_max=1.2, custom_character=False, model_id=model_id,
                framing=framing, requested_size=size,
                approximation_notice='Recreación generada con IA; no reconstruye una fotografía real del pasado.')
