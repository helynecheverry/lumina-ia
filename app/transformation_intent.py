"""Resolve user-described creatures without limiting generation to catalog cards."""
import re
import unicodedata
from app.character_types import character_profile

VERSION = '4.3.1'
# These are visual prompt expansions, not classifiers or a closed character list.
CREATURES = {
 'snake': (r'serpient\w*|snake\w*|cobra\w*|vibora\w*', 'Serpiente humana',
           'overlapping snake scales integrated into the temples cheeks and neck, reptilian eyes with vertical slit pupils, visible serpentine facial details'),
 'wolf': (r'lobo\w*|loba\w*|wolf|wolves|werewolf', 'Lobo humano',
          'prominent wolf ears, gray and silver fur integrated along the cheeks and neck, wolf-like eyes, recognizable human facial center'),
 'tiger': (r'tigre\w*|tiger\w*', 'Tigre humano',
           'rounded tiger ears, clearly visible orange and black striped fur integrated along the outer face and neck, fine whiskers'),
 'fox': (r'zorro\w*|zorra\w*|fox\w*', 'Zorro humano',
         'prominent upright fox ears, clearly visible orange and cream fur on the outer cheeks and sideburns, distinct whiskers'),
 'cat': (r'gato\w*|gata\w*|felin\w*|cat|feline', 'Felino humano',
         'clearly visible feline ears, fine whiskers, short fur integrated into the outer cheeks, feline pupils'),
 'dragon': (r'dragon\w*|dracon\w*', 'Dragón humano',
            'prominent small dragon horns, iridescent scales across the temples cheekbones and neck, reptilian eyes, recognizable human face'),
 'bird': (r'aves?|pajar(?:o|a)s?|birds?|avian', 'Ave humana',
          'colorful feather crest and feathers integrated into the temples and shoulders, avian eye details, human nose and mouth'),
 'octopus': (r'pulpo\w*|octopus|octopi', 'Pulpo humano',
             'iridescent textured skin and small organic tentacles with suction cups integrated around the outer head and shoulders, human facial center'),
 'jellyfish': (r'medusa\w*|jellyfish', 'Medusa humana',
               'translucent bioluminescent jellyfish structures and delicate glowing tendrils around a recognizable human face'),
 'shark': (r'tiburon\w*|shark\w*', 'Tiburón humano',
           'subtle gill slits along the neck, gray shark-like skin texture, small dorsal crest, human facial proportions'),
 'butterfly': (r'mariposa\w*|butterfl\w*', 'Mariposa humana',
               'visible patterned butterfly wings behind the shoulders, delicate antennae and colorful wing-scale markings at the temples'),
 'robot': (r'robot\w*|cyborg\w*|ciborg\w*', 'Cíborg humano',
           'clearly visible mechanical implants integrated into the temple and cheek, metallic neck components, luminous circuitry, human facial center'),
 'plant': (r'planta\w*|arbol\w*|plant|tree', 'Planta humana',
           'organic leaf and bark textures integrated into the cheeks and neck, small branches and leaves framing a recognizable human face'),
}


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c))


def resolve_character(character_type, text='', translated=''):
    base = character_profile(character_type)
    original = normalized(text)
    english = normalized(translated)
    joined = original + ' ' + english
    self_edit = bool(re.search(r'\b(convierteme|convertirme|transformame|transformarme|convert me|turn me|make me|transform the person|transform the reference)\b', joined))
    hybrid = bool(re.search(r'\b(hibrid\w*|hybrid\w*|humanoid\w*|antropomorf\w*|anthropomorphic|human[ao])\b', joined))
    visual_traits = bool(re.search(r'\b(escamas|scales|pelaje|fur|colmillos|fangs|tentaculos|tentacles|cuernos|horns|reptil\w*)\b',joined))
    found = None
    for key,(pattern,label,features) in CREATURES.items():
        for match in re.finditer(r'\b(?:'+pattern+r')\b', joined):
            prefix = joined[max(0,match.start()-65):match.start()]
            if re.search(r'\b(sin|no|without|not)\s+(?:(?:quiero|deseo|want|ser|be|any|una?|an?|de|of|escamas|scales|fur|pelaje)\s+){0,5}$', prefix):
                continue
            if re.search(r"\b(no quiero ser|no deseo ser|do not want to be|don't want to be|no me conviertas en|no me transformes en|do not turn me into)\s+(?:una?\s+|an?\s+)?$",prefix):
                continue
            if re.search(r'\b(estampad\w*|printed|logo|drawing)\b', joined) and not (self_edit or hybrid):
                continue
            decorative = re.search(r'\b(camiseta|camisa|chaqueta|estampado|logo|shirt|jacket|print|fondo|background|backdrop)\b',joined)
            if decorative and not (self_edit or hybrid or visual_traits):
                continue
            found = (key,label,features)
            break
        if found:
            break
    generic_hybrid = bool(re.search(r'\b(hibrid\w*|hybrid\w*|humanoid\w*|antropomorf\w*|anthropomorphic)\b', joined))
    ordinary = {'un','una','ser','persona','person','face','skin','portrait','being','foto','retrato','rostro','cuerpo','piel','con','de','with','natural','normal','realistic','realista'}
    pairs = re.findall(r'\b([a-z]+)\s+human[ao]\b|\bhuman\s+([a-z]+)\b', joined.replace('-', ' '))
    generic_hybrid = generic_hybrid or any((left or right) not in ordinary for left,right in pairs)
    if not found and not self_edit and not generic_hybrid:
        return base, {'custom_character':False, 'resolved_character_type':character_type}
    if re.search(r'\b(no me transformes|do not transform me|no quiero transformarme)\b',joined):
        return base, {'custom_character':False, 'resolved_character_type':character_type}
    intensity = 'strong'
    if re.search(r'\b(sutil\w*|leve\w*|discret\w*|subtle|slight|mild)\b',joined):
        intensity = 'subtle'
    elif re.search(r'\b(extrem\w*|intens\w*|muy marcad\w*|strong|dramatic|full transformation)\b',joined):
        intensity = 'strong'
    elif re.search(r'\b(moderad\w*|equilibrad\w*|marcad\w*|moderate|balanced)\b',joined):
        intensity = 'visible'
    key,label,features = found or ('freeform','Personaje personalizado','the visible character and anatomical changes explicitly described by the user')
    emphasis = {'subtle':'subtle but readable', 'visible':'clearly visible and integrated', 'strong':'pronounced and unmistakable'}[intensity]
    low,high = {'subtle':(.55,1.1),'visible':(.45,.85),'strong':(.35,.7)}[intensity]
    inferred = []
    if key == 'snake':
        colors = r'(?:red|green|blue|yellow|black|white|pink|purple|orange|golden|silver|brown|gray|grey|turquoise|violet)'
        def colored(part):
            return bool(re.search(r'\b'+colors+r'(?:\s+\w+){0,2}\s+'+part+r'\b|\b'+part+r'(?:\s+\w+){0,2}\s+'+colors+r'\b', english))
        skin = 'reptilian' if colored(r'(?:skin|scales|snake|serpent|cobra)') else 'green reptilian'
        irises = 'reptilian irises' if colored(r'(?:eyes|irises)') else 'yellow reptilian irises'
        if skin.startswith('green'): inferred.append('green scales')
        if irises.startswith('yellow'): inferred.append('yellow irises')
        area = 'temples and sides of the neck show fine patches of' if intensity == 'subtle' else 'facial skin and neck are covered in'
        features = (f"The person's own {area} small continuous {skin} scales. "
                    f"Both eyes have {irises} with sharply defined thin vertical black slit pupils. "
                    'The nose, lips and facial layout retain their recognizable human structure')
    profile = dict(base, label=label, visual_features=features, direction=f'{emphasis} transformation: {features}, same reference person with recognizable human facial landmarks',
                   subject='one recognizable human creature hybrid' if found else 'one recognizable person transformed as requested',
                   hair='', accessory='', backbone=None, min_identity=low, max_identity=high,
                   identity_mode='creature_with_identity_cues' if intensity == 'strong' else 'recognizable_transformation', character_version=VERSION,
                   negative='unrelated person, separate animal, animal wrapped around the neck, printed animal on clothing, costume mask, duplicate heads, replacement animal head',
                   edit_scope=f'Make the requested transformation {emphasis}. Integrate the requested skin, eye and anatomical features into the person, rather than adding a separate animal beside them, wrapping an animal around their neck, or adding a printed costume. Retain recognizable facial landmarks and expression while allowing the requested changes.')
    return profile, {'custom_character':True,'resolved_character_type':key,'transformation_intensity':intensity,'inferred_details':inferred}
