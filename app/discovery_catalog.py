"""Curated fantasy universes for local visual affinity and named transformations."""
from pathlib import Path
from app.character_types import character_profile

VERSION='1.0'
ASSETS=Path(__file__).resolve().parents[1]/'web/assets/discovery'
CATEGORIES={
 'pokemon':dict(label='Pokémon',symbol='◓',description='Descubre una afinidad visual y crea tu versión Pokémon.'),
 'digimon':dict(label='Digimon',symbol='✧',description='Encuentra tu compañero digital y transforma tu foto.'),
 'zodiac':dict(label='Zodiaco',symbol='☾',description='Elige una afinidad fantástica o selecciona tu signo. La foto no determina tu signo real.'),
}
# key, name, artwork id, short public description, concrete visual target
POKEMON=[
 ('pikachu','Pikachu',25,'Amarillo, mejillas rojas y energía eléctrica.','bright yellow fur, long pointed ears with black tips, round red cheek markings and small electric sparks'),
 ('eevee','Eevee',133,'Pelaje cálido, orejas grandes y collar de pelo claro.','warm brown fur, large upright ears, a fluffy cream neck ruff and expressive eyes'),
 ('vulpix','Vulpix',37,'Pelaje rojizo y mechones ondulados.','copper red fox fur, curled forehead tufts, pointed fox ears and several flowing curled tails behind the shoulders'),
 ('lucario','Lucario',448,'Azul y negro con rasgos de chacal.','blue and black jackal-like fur, upright ears, dark facial markings and small steel chest accents'),
 ('charizard','Charizard',6,'Dragón naranja con alas y fuego.','orange draconic skin, two small backward horns, broad blue-inner dragon wings behind the shoulders and a warm flame glow'),
 ('squirtle','Squirtle',7,'Azul acuático con caparazón y formas redondeadas.','smooth aqua blue skin, large rounded eyes, a cream turtle chest plate and a brown turtle shell'),
 ('bulbasaur','Bulbasaur',1,'Tonos verde agua, manchas y una planta a la espalda.','turquoise green skin with darker patches, small pointed ears, red eyes and a large green plant bulb behind the shoulders'),
 ('gengar','Gengar',94,'Violeta, contornos puntiagudos y sonrisa traviesa.','deep purple skin, a spiky rounded silhouette, red luminous eyes and a broad mischievous human-readable grin'),
 ('jigglypuff','Jigglypuff',39,'Rosa, ojos grandes y un mechón curvado.','soft pink skin or fine pink fur, large teal eyes, small triangular ears and a curled pink forehead tuft'),
 ('mewtwo','Mewtwo',150,'Plateado y violeta con silueta psíquica.','smooth pale silver skin, lavender accents, sleek feline cranial ridges and a luminous violet psychic aura'),
 ('gardevoir','Gardevoir',282,'Verde y blanco con un estilo elegante.','emerald green swept hair-like head crest, pale white flowing layered garments, a small red chest accent and graceful humanoid features'),
 ('dragonite','Dragonite',149,'Dragón cálido con antenas y alas pequeñas.','warm orange dragon skin, two slim head antennae, cream chest scales and small green-inner wings'),
 ('arcanine','Arcanine',59,'Naranja, rayas oscuras y una melena clara.','orange canine fur with black stripes, a large flowing cream mane, upright ears and expressive canine eyes'),
 ('meowth','Meowth',52,'Crema, bigotes y un detalle dorado en la frente.','cream feline fur, pointed ears, long fine whiskers and an oval golden forehead ornament'),
 ('psyduck','Psyduck',54,'Amarillo, formas suaves y aire de pato.','warm yellow fine feathers, a broad duck-like nose, three dark head tufts and expressive round eyes'),
 ('lapras','Lapras',131,'Azul marino, aletas y detalles nacarados.','ocean blue skin, curled ear fins, a small forehead horn, cream neck scales and a pearly shell behind the shoulders'),
]
DIGIMON=[
 ('agumon','Agumon','Dinosaurio amarillo con garras claras.','golden yellow dinosaur skin, a rounded reptilian muzzle, green eyes and ivory claws'),
 ('gabumon','Gabumon','Pelaje azul y blanco con un cuerno.','a blue and white striped wolf pelt framing the face, a single small horn and warm yellow skin visible at the facial center'),
 ('patamon','Patamon','Naranja y crema con orejas como alas.','soft orange and cream fur, large wing-like ears and bright blue eyes'),
 ('gatomon','Gatomon','Felino blanco con detalles violetas.','white feline fur, large pointed ears with purple accents, blue eyes and oversized striped golden gloves'),
 ('tentomon','Tentomon','Escarabajo rojo con ojos verdes.','red beetle-like armor, large green compound-eye details, a small forehead horn and segmented insect accents'),
 ('palmon','Palmon','Criatura vegetal con una flor rosa.','green plant-like skin, leafy neck details, vine-like hands and a large pink flower crowning the head'),
 ('gomamon','Gomamon','Blanco, ojos verdes y una cresta naranja.','soft white aquatic mammal fur, green eyes, purple cheek markings and an orange crest'),
 ('biyomon','Biyomon','Ave rosada con mechón y plumas claras.','soft pink feathers, a curved head crest, small bird-like beak details and blue-tipped wings'),
 ('salamon','Salamon','Criatura pequeña de pelaje crema y ojos azules.','soft cream puppy-like fur, large floppy ears, bright blue eyes and a small golden neck ring'),
 ('elecmon','Elecmon','Rojo y azul con grandes orejas.','deep red fur, cobalt blue stripes and accents, large upright ears and expressive eyes'),
 ('hawkmon','Hawkmon','Ave rojiza con plumas y detalles blancos.','rust red and cream feathers, an upright feather crest, fine avian facial details and broad wings'),
 ('armadillomon','Armadillomon','Armadura dorada y rostro redondeado.','golden yellow segmented armadillo armor, a rounded friendly face, green eyes and clawed hands'),
]
ZODIAC=[
 ('aries','Aries','♈','Fuego y cuernos de carnero.','a fiery humanoid ram guardian with curved ram horns and warm red and gold accents'),
 ('taurus','Tauro','♉','Tierra, cuernos y texturas minerales.','a humanoid bull guardian with strong curved bull horns, emerald and bronze earth textures'),
 ('gemini','Géminis','♊','Dualidad y reflejos celestes.','a single celestial humanoid with a balanced dual-color face design, mirrored silver and gold costume details'),
 ('cancer','Cáncer','♋','Luna, agua y armadura nacarada.','a lunar humanoid with pearlescent crab-inspired armor, small coral-like details and a silver ocean glow'),
 ('leo','Leo','♌','Melena, sol y tonos dorados.','a solar humanoid lion with a flowing golden mane, warm amber eyes and sun-like ornaments'),
 ('virgo','Virgo','♍','Naturaleza y detalles de espigas.','a celestial nature guardian with delicate leaf and wheat motifs, cream and sage green tones'),
 ('libra','Libra','♎','Simetría, metal claro y equilibrio visual.','a celestial humanoid with symmetrical silver and pale blue armor, delicate golden scale ornaments'),
 ('scorpio','Escorpio','♏','Oscuridad y armadura de escorpión.','a dark humanoid scorpion guardian with obsidian segmented armor, red luminous accents and a curved tail behind the shoulders'),
 ('sagittarius','Sagitario','♐','Arquero cósmico y tonos violetas.','a cosmic humanoid archer with violet and bronze armor, star-like markings and a luminous bow'),
 ('capricorn','Capricornio','♑','Cuernos de cabra y escamas marinas.','a mystical humanoid sea-goat guardian with curved goat horns, dark teal scales and silver accents'),
 ('aquarius','Acuario','♒','Agua luminosa y detalles azulados.','a celestial humanoid water bearer with flowing aqua hair-like details, blue luminous skin patterns and translucent water ornaments'),
 ('pisces','Piscis','♓','Aletas, escamas y colores iridiscentes.','a celestial humanoid fish guardian with delicate fin-like ears, iridescent teal and violet scales'),
]
ENTRIES={}
for key,name,pokedex,summary,features in POKEMON:
 ENTRIES['pokemon:'+key]=dict(id='pokemon:'+key,category='pokemon',key=key,name=name,summary=summary,features=features,symbol='◓',artwork_id=pokedex)
for key,name,summary,features in DIGIMON:
 ENTRIES['digimon:'+key]=dict(id='digimon:'+key,category='digimon',key=key,name=name,summary=summary,features=features,symbol='✧')
for key,name,symbol,summary,features in ZODIAC:
 ENTRIES['zodiac:'+key]=dict(id='zodiac:'+key,category='zodiac',key=key,name=name,summary=summary,features=features,symbol=symbol)


def get_inspiration(identifier):
 if identifier not in ENTRIES:raise ValueError('Elige un personaje válido del universo seleccionado.')
 return ENTRIES[identifier]


def public_catalog():
 result={}
 for key,category in CATEGORIES.items():
  items=[]
  for item in ENTRIES.values():
   if item['category']!=key:continue
   image=ASSETS/key/(item['key']+'.png')
   items.append({k:item[k] for k in ('id','category','key','name','summary','symbol')}|{'image':f'/assets/discovery/{key}/{image.name}' if image.is_file() else None})
  result[key]=dict(category,items=items)
 return result


def inspiration_profile(character_type,identifier,text='',translated=''):
 from app.transformation_intent import resolve_character
 item=get_inspiration(identifier)
 _,intent=resolve_character(character_type,text,translated)
 intensity=intent.get('transformation_intensity','strong')
 category=CATEGORIES[item['category']]['label']
 base=character_profile(character_type)
 profile=dict(base,label=item['name']+' · '+category,visual_features=item['features'],direction='a humanoid creature inspired by '+item['name']+', '+item['features'],subject='one humanoid creature based on the reference person',hair='',accessory='',backbone=None,min_identity=.35,max_identity=.8,identity_mode='creature_with_identity_cues',character_version='discovery-'+VERSION,negative='unrelated person, duplicate heads, printed character on clothing, mascot costume',reference_context=1.65)
 return profile,dict(custom_character=True,resolved_character_type='inspiration',transformation_intensity=intensity,inferred_details=[],inspiration_id=identifier,inspiration_name=item['name'],inspiration_category=item['category'])
