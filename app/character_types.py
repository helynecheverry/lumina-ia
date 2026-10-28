"""Identity-preserving character features applied to the uploaded human face."""
CHARACTER_VERSION = '3.2'
IDENTITY_DIRECTION = ('same person as the reference, recognizable original human face, '
                      'original facial proportions, original eyes nose mouth and jawline')
# Each transformation is a partial enhancement, never a replacement animal head.
FEATURES = [
 ('natural','Natural','Conserva tu rostro y proporciones naturales.',
  'natural human appearance, realistic facial proportions, understated character styling','',.12),
 ('bold','Atrevido','Tu mismo rostro con estilismo atrevido y expresión segura.',
  'bold avant-garde fashion styling, confident expression, dramatic fashion makeup','expressive fashion hairstyle',.08),
 ('extreme','Extremo','Tu rostro reconocible con estilismo fantástico más intenso.',
  'eccentric surreal fashion styling, exaggerated costume details, playful makeup design','imaginative sculptural hairstyle',.02),
 ('elf','Elfo','Tu rostro con orejas puntiagudas y detalles élficos.',
  'human with pointed elf ears, delicate elven markings at temples','',.08),
 ('cyborg','Cíborg','Tu rostro visible con pequeños implantes mecánicos integrados.',
  'human cyborg with small metallic implants at one temple and cheek, subtle glowing circuitry, most facial skin visible','',.08),
 ('vampire','Vampiro','Tu rostro con colmillos discretos y detalles góticos.',
  'human vampire, small canine fangs, subtle gothic eye makeup, slightly pale skin','',.08),
 ('fairy','Hada','Tu rostro con detalles luminosos, orejas sutiles y alas.',
  'human fairy, delicate luminous freckles, small pointed ears, translucent wings behind shoulders','',.08),
 ('cat','Felino','Tu rostro humano con orejas felinas, bigotes y pelaje sutil en las mejillas.',
  'human with feline features, small cat ears above original hair, fine whiskers, subtle short fur at cheeks, original human nose and lips','',.05),
 ('fox','Zorro','Tu rostro humano con orejas de zorro visibles, bigotes y pelaje naranja y blanco en los laterales.',
  'recognizable human person with prominent upright fox ears beside the original hairstyle, orange and cream short fur patches restricted to the sideburns and outer cheeks, clearly visible whiskers, unchanged original human hair and bare forehead, original human nose lips and jawline','',.05),
 ('dragon','Dragón','Tu rostro con escamas localizadas, pequeños cuernos y ojos dracónicos.',
  'human with draconic features, small horns at temples, iridescent scale patches along cheekbones, subtly reptilian irises, original human nose and mouth','',.05),
 ('bird','Ave','Tu rostro con plumas en las sienes, cresta y detalles de ave.',
  'human with avian features, colorful feathers at temples and eyebrows, small feather crest, original human nose lips and jawline','',.05),
 ('alien','Alien','Tu rostro con matices extraterrestres y marcas luminosas.',
  'human with subtle extraterrestrial features, faint blue skin tint, luminous temple markings, original human eye shape nose mouth and skull proportions','',.05),
]
CHARACTER_TYPES = {}
for key,label,description,features,hair,offset in FEATURES:
    CHARACTER_TYPES[key] = dict(label=label,description=description,
        direction=features+', '+IDENTITY_DIRECTION,hair=hair,accessory='',
        subject='one recognizable human person',
        negative='replacement face, animal head, full animal muzzle, mascot head, full face mask, unrelated person',
        reference_context=1.65,identity_offset=offset,min_identity=.65 if key not in ('natural','bold','extreme') else .3,max_identity=1.2,
        backbone=None,identity_mode='preserve_human_face',character_version=CHARACTER_VERSION,
        preview=f'/characters/{key}.png?v={CHARACTER_VERSION}')
for key in ('cat','fox','dragon','bird','alien'):
    CHARACTER_TYPES[key]['preferred_model']='flux_klein'

CHARACTER_TYPES['fox']['edit_scope']='Keep the original hairstyle and the entire forehead unchanged, with bare human skin on the forehead, nose, lips and chin. Restrict the transformation to two prominent upright fox ears beside the hair, clearly visible short orange and cream fur patches at the sideburns and outer cheeks, and whiskers. Keep the facial center human. No fur on the forehead, animal muzzle or replacement animal head.'

CHARACTER_TYPES['fox']['character_version']='3.4'

CHARACTER_TYPES['natural']['negative'] += ', exaggerated caricature, theatrical costume'
CHARACTER_TYPES['vampire']['negative'] += ', blood, gore, wounds'
CHARACTER_TYPES['bird']['negative'] += ', long beak, bird skull'


def character_profile(character_type):
    if character_type not in CHARACTER_TYPES:
        raise ValueError('Tipo de personaje inválido. Elige una opción del catálogo.')
    return CHARACTER_TYPES[character_type]
