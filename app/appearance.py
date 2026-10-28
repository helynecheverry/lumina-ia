"""Validated visual controls, separate from free text and style defaults."""
CONTROLS = {
 'presentation': {'label':'Presentación','options':{
    'feminine':('Femenina','feminine presentation, woman'),
    'masculine':('Masculina','masculine presentation, man'),
    'androgynous':('Andrógina','androgynous presentation')}},
 'outfit': {'label':'Vestuario','options':{
    'black_suit':('Traje de sastrería negro','tailored black suit'),
    'beige_blazer':('Blazer de lino beige','beige linen blazer'),
    'silk_dress':('Vestido de seda champán','champagne silk dress'),
    'red_jacket':('Chaqueta roja','red jacket'),
    'blue_jacket':('Chaqueta azul','blue jacket'),
    'white_suit':('Traje blanco','white suit'),
    'gold_dress':('Vestido dorado','golden dress'),
    'yellow_hoodie':('Sudadera amarilla','yellow hoodie'),
    'silver_armor':('Armadura plateada','silver armor'),
    'spacesuit':('Traje espacial','white astronaut spacesuit'),
    'superhero_suit':('Traje de superhéroe','colorful superhero suit')}},
 'scene': {'label':'Escenario','options':{
    'white_studio':('Fondo blanco','plain white studio background'),
    'blue_studio':('Fondo azul','plain blue studio background'),
    'beach':('Playa al atardecer','beach background at sunset'),
    'future_city':('Ciudad futurista','futuristic city background'),
    'forest':('Bosque mágico','enchanted forest background'),
    'spaceship':('Nave espacial','spaceship interior background'),
    'concert':('Concierto','concert stage background')}},
 'lighting': {'label':'Iluminación','options':{
    'soft_studio':('Estudio suave','soft diffused studio lighting'),
    'neon':('Neón rosa y azul','pink and blue neon lighting'),
    'golden':('Atardecer dorado','warm golden hour lighting'),
    'dramatic':('Cine dramático','dramatic cinematic lighting'),
    'natural':('Luz natural','soft natural daylight')}},
}


def validate_appearance(value):
    if value is None:
        return {}
    if not isinstance(value, dict) or set(value)-set(CONTROLS):
        raise ValueError('Opciones visuales inválidas')
    result = {}
    for name, option in value.items():
        if not isinstance(option, str):
            raise ValueError('Opción visual inválida')
        if not option:
            continue
        if option not in CONTROLS[name]['options']:
            raise ValueError('Opción inválida de '+CONTROLS[name]['label'])
        result[name] = option
    return result


def public_controls():
    return {key:{'label':item['label'],'options':{option:{'label':values[0]}
            for option,values in item['options'].items()}} for key,item in CONTROLS.items()}
