"""Streamlit portrait studio. Calls only the local API; no model is loaded here."""
import base64
import hashlib
import io
import json
import random
import uuid
from pathlib import Path

import requests
import streamlit as st
from PIL import Image, ImageOps

ASSETS = Path(__file__).resolve().parent / 'assets' / 'portraits'


def choose_style(value=None):
    if value is not None:
        st.session_state['portrait_preset'] = value
    st.session_state['portrait_identity'] = .5 if st.session_state.get('portrait_preset') == 'illustration' else .8


def studio(api):
    try:
        config = api('GET', '/influencer/config', timeout=10).json()
    except (requests.RequestException, RuntimeError) as exc:
        st.error(f'No se pudo conectar con el estudio: {exc}')
        return
    st.caption('LÚMINA ID / ESTUDIO PERSONAL · SIN CRÉDITOS · SIN SUBIR TU FOTO A OTROS SERVICIOS')
    st.title('Tú, en otra historia.')
    st.write('Toma una foto. Elige un universo. Crea un retrato nuevo con tu rostro como referencia.')
    st.markdown('''<div style="display:flex;gap:10px;flex-wrap:wrap;margin:20px 0 28px">
    <span class="studio-chip">◉ Cámara o archivo</span><span class="studio-chip">✦ 6 direcciones creativas</span>
    <span class="studio-chip">↗ Generación local</span><span class="studio-chip">▧ Galería personal</span></div>''', unsafe_allow_html=True)
    if not config['ready']:
        st.warning('El estudio se está preparando. Comprueba los pesos locales y la disponibilidad de CUDA.')
    controls, stage = st.columns([1, 1.6], gap='large')
    with controls:
        with st.container(border=True):
            st.subheader('01 · Tu referencia')
            source = st.segmented_control('Cómo quieres empezar', ['Subir foto', 'Usar cámara'], default='Subir foto')
            if source == 'Usar cámara':
                uploaded = st.camera_input('Mira a la cámara', key='portrait_camera')
                st.caption('La cámara se activa con tu permiso en este navegador.')
            else:
                uploaded = st.file_uploader('Arrastra tu foto aquí', type=['png', 'jpg', 'jpeg', 'webp'],
                                            max_upload_size=10, key='portrait_upload')
            raw = uploaded.getvalue() if uploaded else None
            if raw:
                try:
                    preview = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert('RGB')
                    preview.thumbnail((400, 400))
                    st.image(preview, caption='Tu foto de referencia', width='stretch')
                except Exception:
                    st.error('No fue posible abrir la imagen.')
                    raw = None
            st.caption('Una sola persona, de frente y con buena luz. El parecido puede variar entre resultados.')
        with st.container(border=True):
            st.subheader('02 · Tu dirección creativa')
            preset = st.selectbox('Elige el estilo', list(config['presets']),
                                 format_func=lambda key: config['presets'][key]['label'], key='portrait_preset', on_change=choose_style)
            st.caption(config['presets'][preset]['description'])
            prompt = st.text_area('Hazlo más tuyo (opcional)', placeholder='Ej.: blue jacket, city at sunset, soft lighting',
                                  max_chars=500, height=90)
            st.caption('Los estilos ya incluyen su descripción. Para cambios precisos, escribe los detalles en inglés.')
            with st.expander('Ajustes de creación'):
                if 'portrait_identity' not in st.session_state:
                    st.session_state['portrait_identity'] = .8
                identity = st.slider('Influencia del rostro', min_value=.3, max_value=1.2, step=.05, key='portrait_identity',
                                     help='Más alto sigue más la referencia; más bajo permite variar el estilo.')
                quality = st.select_slider('Detalle', options=['Ágil · 16 pasos', 'Equilibrado · 24 pasos', 'Detallado · 32 pasos'],
                                          value='Equilibrado · 24 pasos')
                steps = {'Ágil · 16 pasos': 16, 'Equilibrado · 24 pasos': 24, 'Detallado · 32 pasos': 32}[quality]
                random_seed = st.checkbox('Sorpréndeme con una variación', value=True)
                manual_seed = st.number_input('Semilla reproducible', 0, 2147483647, 9241, disabled=random_seed)
            signature = hashlib.sha256((raw or b'') + json.dumps([preset, prompt, identity, steps, random_seed, manual_seed]).encode()).hexdigest()
            if st.session_state.get('portrait_signature') != signature:
                st.session_state['portrait_signature'] = signature
                st.session_state['portrait_request_key'] = str(uuid.uuid4())
                st.session_state['portrait_seed'] = random.SystemRandom().randint(0, 2147483647) if random_seed else int(manual_seed)
            create = st.button('✦ Crear mi retrato', type='primary', width='stretch', disabled=not raw or not config['ready'])
            st.caption('512 × 512 px · Sin costo por generación · El tiempo depende de la GPU y de la cola.')
            if create:
                try:
                    job = api('POST', '/influencer/generations', files={'file': (uploaded.name, raw, uploaded.type)},
                              data={'preset': preset, 'prompt': prompt, 'identity_strength': identity, 'steps': steps,
                                    'seed': st.session_state['portrait_seed'],
                                    'request_key': st.session_state['portrait_request_key']}, timeout=30).json()
                    st.session_state['portrait_job'] = job['id']
                    st.query_params['creation'] = job['id']
                    # Same button may intentionally produce another variation after this one.
                    st.session_state['portrait_request_key'] = str(uuid.uuid4())
                    if random_seed:
                        st.session_state['portrait_seed'] = random.SystemRandom().randint(0, 2147483647)
                except (requests.RequestException, RuntimeError) as exc:
                    st.error(str(exc))
    with stage:
        st.subheader('03 · Tu próxima versión')
        job_id = st.session_state.get('portrait_job') or st.query_params.get('creation')
        if job_id:
            render_job(api, job_id)
        else:
            with st.container(border=True):
                example = ASSETS / (preset + '.png')
                if example.is_file():
                    st.image(str(example), caption='Ejemplo generado localmente con una fotografía pública de referencia', width='stretch')
                else:
                    spec = config['presets'][preset]
                    st.markdown(f'''<div class="portrait-placeholder" style="--portrait-accent:{spec['color']}">
                    <div class="portrait-orbit">{spec['icon']}</div><p>UNA FOTO. MUCHAS VERSIONES.</p>
                    <h2>{spec['label']}</h2><span>{spec['description']}</span></div>''', unsafe_allow_html=True)
                st.caption('Tu resultado aparecerá aquí. Puedes seguir trabajando mientras se genera.')
        st.markdown('**Un estilo para cada versión de ti**')
        for start in range(0, len(config['presets']), 3):
            columns = st.columns(3)
            for column, (key, spec) in zip(columns, list(config['presets'].items())[start:start + 3]):
                with column, st.container(border=True):
                    example = ASSETS / (key + '.png')
                    if example.is_file():
                        st.image(str(example), width='stretch')
                    st.button(spec['icon'] + ' ' + spec['label'], key='style_' + key, width='stretch',
                              on_click=choose_style, args=(key,))
        display_model = 'Stable Diffusion 1.5 + IP-Adapter Plus Face' if preset == 'illustration' else config['model']
        st.caption('Motor local: ' + display_model + '. El parecido puede variar entre resultados.')


@st.fragment(run_every=3)
def render_job(api, job_id):
    try:
        job = api('GET', '/influencer/generations/' + job_id, timeout=10).json()
    except (requests.RequestException, RuntimeError) as exc:
        st.error(str(exc))
        return
    if job['status'] in ('queued', 'processing'):
        st.progress(job['progress'] / 100, text=job['message'])
        st.caption('Puedes recargar la página: la creación queda guardada en MongoDB.')
        if st.button('Cancelar creación', key='cancel_' + job_id):
            try:
                api('POST', '/influencer/generations/' + job_id + '/cancel', timeout=10)
                st.rerun(scope='fragment')
            except (requests.RequestException, RuntimeError) as exc:
                st.error(str(exc))
    elif job['status'] == 'completed':
        result_key = 'portrait_image_' + job_id
        if result_key not in st.session_state:
            try:
                st.session_state[result_key] = api('GET', '/image/' + job_id, params={'kind': 'generations'}, timeout=30).content
            except (requests.RequestException, RuntimeError) as exc:
                st.error(str(exc))
                return
        output = st.session_state[result_key]
        st.image(output, caption='Tu retrato generado con IA', width='stretch')
        a, b = st.columns(2)
        a.download_button('↓ Descargar retrato', output, 'lumina-' + job['preset'] + '.png', 'image/png',
                          width='stretch', key='download_' + job_id)
        if b.button('Llevar al editor', width='stretch', key='editor_' + job_id):
            st.session_state['restored'] = output
            st.success('Disponible en Laboratorio creativo → Último resultado.')
        upscale_key = 'portrait_upscale_' + job_id
        if st.button('✦ Mejorar detalle ×2 con Real-ESRGAN', key='upscale_' + job_id, width='stretch'):
            try:
                with st.spinner('Ampliando tu creación; espera si la GPU está ocupada…'):
                    enlarged = api('POST', '/restore', files={'file': ('portrait.png', output, 'image/png')},
                                   data={'scale': 2}, timeout=600).json()
                st.session_state[upscale_key] = base64.b64decode(enlarged['image_base64'])
            except (requests.RequestException, RuntimeError) as exc:
                st.error(str(exc))
        if upscale_key in st.session_state:
            st.download_button('↓ Descargar versión 1024 × 1024', st.session_state[upscale_key],
                               'lumina-hd.png', 'image/png', key='hd_' + job_id, width='stretch')
        a.metric('Generación', f"{job.get('seconds', 0):.1f} s")
        b.metric('Tamaño', '512 × 512')
        st.caption(f"Guardado localmente · Semilla {job['seed']} · ID {job_id}")
    else:
        st.warning(job['message'])


def gallery(api):
    try:
        jobs = api('GET', '/history', params={'kind': 'generations'}, timeout=10).json()
        if not jobs:
            st.info('Tu historia empieza con una foto. Crea tu primer retrato para verlo aquí.')
            return
        status_names = {'queued': 'En cola', 'processing': 'Creando', 'completed': 'Lista', 'failed': 'Error',
                        'cancelled': 'Cancelada', 'interrupted': 'Interrumpida'}
        for start in range(0, len(jobs), 3):
            for column, job in zip(st.columns(3), jobs[start:start + 3]):
                with column, st.container(border=True):
                    st.markdown('**' + job.get('preset', 'Retrato').title() + '**')
                    st.caption(status_names.get(job['status'], job['status']) + ' · ' + job['created_at'][:16])
                    if job.get('has_image'):
                        image = api('GET', '/image/' + job['id'], params={'kind': 'generations'}, timeout=30).content
                        st.image(image, width='stretch')
                        st.download_button('Descargar', image, 'lumina-' + job['id'] + '.png', 'image/png', key='gallery_' + job['id'])
                    else:
                        st.caption(job.get('message', ''))
                    st.link_button('Abrir creación', '?creation=' + job['id'])
    except (requests.RequestException, RuntimeError) as exc:
        st.error(str(exc))
