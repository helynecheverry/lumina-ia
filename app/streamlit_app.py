import base64
import io
from influencer_ui import studio, gallery
import os
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
from PIL import Image
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / '.env')
API = os.getenv('API_URL', 'http://127.0.0.1:8000')
st.set_page_config(page_title='Lúmina · Estudio de imágenes', page_icon='✦', layout='wide')
st.markdown('''<style>
.stApp {background:radial-gradient(ellipse at top right,#18263a 0%,#0d111b 65%);color:#edf2fa}
.block-container{max-width:1400px;padding-top:2.5rem}
.studio-chip{border:1px solid #394154;border-radius:100px;padding:8px 14px;font-size:.8rem;color:#c1c9d9}
.portrait-placeholder{padding:60px 28px;text-align:center;min-height:420px;display:flex;flex-direction:column;align-items:center;justify-content:center;background:radial-gradient(ellipse at 50% 40%,#37304a,#141b2b 70%);border-radius:14px}
.portrait-placeholder h2{color:var(--portrait-accent)}
.portrait-placeholder p{font-size:.7rem;letter-spacing:.2em;color:#a5afc1}
.portrait-placeholder span{color:#b7c1d4;max-width:300px}
.portrait-orbit{width:120px;height:120px;border:1px solid var(--portrait-accent);border-radius:60px;font-size:4rem;color:var(--portrait-accent);margin-bottom:24px}

h1{font-size:3.4rem!important;letter-spacing:-.06em} h2,h3{letter-spacing:-.03em}
[data-testid="stMetric"]{background:#182234;border:1px solid #2b3a50;border-radius:16px;padding:18px}
[data-testid="stSidebar"]{background:#101725} button[kind="primary"]{background:#b8f468;color:#13200b;border:0}
[data-testid="stFileUploader"]{border:1px dashed #526780;border-radius:16px}
</style>''', unsafe_allow_html=True)


def api(method, path, **kwargs):
    response = requests.request(method, API + path, timeout=kwargs.pop('timeout', 600), **kwargs)
    if not response.ok:
        try:
            message = response.json().get('detail', response.reason)
        except ValueError:
            message = response.reason
        raise RuntimeError(message)
    return response


def compare(before, after, name):
    left, right = st.columns(2)
    left.image(before, caption='ORIGINAL', width='stretch')
    right.image(after, caption='RESULTADO', width='stretch')
    st.download_button('Descargar PNG', after, name, 'image/png', key=name)


with st.sidebar:
    st.markdown('## ✦ Lúmina')
    st.caption('TU ESTUDIO CREATIVO · 100% LOCAL')
    page = st.radio('Espacio de trabajo', ['Crear con mi foto', 'Mejorar imagen', 'Laboratorio creativo', 'Mi galería'])
    st.divider()
    try:
        status = api('GET', '/health', timeout=5).json()
        st.success('API conectada')
        st.caption(f"MongoDB: {status['mongodb']} · Modelo: {status['model']}")
        st.caption(f"Motor: {status['device'].upper()} · Máximo: {status['max_upload_mb']} MB")
    except requests.RequestException:
        st.error('API sin conexión. Inicia scripts/start.sh.')
    except RuntimeError as exc:
        st.error(str(exc))
    st.divider()
    st.caption('La superresolución puede generar detalles nuevos. Revisa siempre el resultado.')

if page != 'Crear con mi foto':
    st.caption('✦ DE UNA IMAGEN A NUEVAS POSIBILIDADES')
    st.title('Más detalle. Más posibilidades.')
    st.write('Amplía tus fotografías, explora estilos y guarda cada resultado en tu galería.')
    st.divider()

if page == 'Crear con mi foto':
    studio(api)
elif page == 'Mejorar imagen':
    controls, workspace = st.columns([1, 2], gap='large')
    with controls:
        st.subheader('01 / Prepara tu imagen')
        uploaded = st.file_uploader('JPG, PNG o WebP · hasta 10 MB', type=['jpg', 'jpeg', 'png', 'webp'], max_upload_size=int(os.getenv('MAX_UPLOAD_MB', '10')))
        scale = st.select_slider('Ampliación', options=[1, 1.5, 2, 2.5, 3, 3.5, 4], value=2)
        st.caption('El modelo procesa internamente a ×4. Usa imágenes de hasta 3 MP para este equipo.')
        process = st.button('✦ Mejorar y guardar', type='primary', disabled=uploaded is None, width='stretch')
    with workspace:
        st.subheader('02 / Compara el resultado')
        if uploaded:
            raw = uploaded.getvalue()
            signature = (raw, scale)
            if process:
                try:
                    with st.spinner('La GPU está reconstruyendo tu imagen…'):
                        data = api('POST', '/restore', files={'file': (uploaded.name, raw, uploaded.type)}, data={'scale': scale}).json()
                    st.session_state['restoration'] = (signature, data)
                    st.session_state['restored'] = base64.b64decode(data['image_base64'])
                except (requests.RequestException, RuntimeError) as exc:
                    st.error(str(exc))
            cached = st.session_state.get('restoration')
            if cached and cached[0] == signature:
                data = cached[1]
                compare(raw, base64.b64decode(data['image_base64']), 'restaurada.png')
                a, b, c = st.columns(3)
                a.metric('Salida', ' × '.join(map(str, data['output_size'])))
                b.metric('Tiempo', f"{data['seconds']:.2f} s")
                c.metric('Motor', data['device'].upper())
                st.caption(f"Guardada en MongoDB · {data['id']}")
            else:
                st.image(raw, caption='Vista previa', width='stretch')
        else:
            st.info('Tu próxima transformación empieza aquí. Sube una fotografía para comparar el antes y el después.')
            st.markdown('### Retratos · Productos · Fotografías antiguas')
            st.write('Recupera tamaño para impresión, prepara imágenes para catálogos o experimenta con tus archivos.')

elif page == 'Laboratorio creativo':
    st.subheader('Transforma una imagen en algo nuevo')
    labels = {'none': 'Sin filtro', 'denoise': 'Reducir ruido', 'sharpen': 'Más nitidez', 'blur': 'Desenfoque',
              'grayscale': 'Blanco y negro', 'sketch': 'Boceto a lápiz', 'edges': 'Mapa de contornos'}
    mode = st.radio('Origen', ['Subir imagen', 'Último resultado'], horizontal=True)
    uploaded = st.file_uploader('Imagen para crear', type=['jpg', 'jpeg', 'png', 'webp'], max_upload_size=int(os.getenv('MAX_UPLOAD_MB', '10')), key='creative') if mode == 'Subir imagen' else None
    raw = uploaded.getvalue() if uploaded else st.session_state.get('restored') if mode == 'Último resultado' else None
    left, right = st.columns([1, 2], gap='large')
    with left:
        brightness = st.slider('Brillo', -100, 100, 0)
        contrast = st.slider('Contraste', .2, 3., 1., .1)
        selected = st.selectbox('Estilo', list(labels), format_func=labels.get)
        save = st.checkbox('Guardar en mi galería', value=True)
        apply = st.button('Crear resultado', type='primary', disabled=raw is None)
    with right:
        signature = (raw, brightness, contrast, selected, save)
        if apply:
            try:
                with st.spinner('Creando…'):
                    data = api('POST', '/edit', files={'file': (uploaded.name if uploaded else 'restored.png', raw, uploaded.type if uploaded else 'image/png')},
                               data={'brightness': brightness, 'contrast': contrast, 'filter_name': selected, 'save_result': str(save).lower()}).json()
                st.session_state['creative_result'] = (signature, data)
            except (requests.RequestException, RuntimeError) as exc:
                st.error(str(exc))
        cached = st.session_state.get('creative_result')
        if raw and cached and cached[0] == signature:
            compare(raw, base64.b64decode(cached[1]['image_base64']), 'creativa.png')
            if cached[1]['saved']:
                st.success('Creación guardada en MongoDB')
        elif raw:
            st.image(raw, caption='Tu lienzo', width='stretch')
        else:
            st.info('Sube una imagen o usa tu última reconstrucción.')
else:
    st.subheader('Tu galería de resultados')
    collection = st.segmented_control('Tipo de galería', ['Retratos creativos', 'Restauraciones y ediciones'], default='Retratos creativos')
    if collection == 'Retratos creativos':
        gallery(api)
        st.stop()
    kind = st.radio('Colección', ['jobs', 'edits'], format_func=lambda x: 'Mejoras con IA' if x == 'jobs' else 'Creaciones y ediciones', horizontal=True)
    try:
        rows = api('GET', '/history', params={'kind': kind}, timeout=10).json()
        if rows:
            a, b = st.columns(2)
            a.metric('Resultados recientes', len(rows))
            if kind == 'jobs':
                b.metric('Tiempo medio', f"{sum(r['seconds'] for r in rows)/len(rows):.2f} s")
            st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)
            selected = st.selectbox('Abrir resultado', rows, format_func=lambda row: f"{row['filename']} · {row['created_at'][:19]}")
            if st.button('Ver imagen'):
                content = api('GET', '/image/' + selected['id'], params={'kind': kind}, timeout=30).content
                st.session_state['gallery_result'] = (kind, selected['id'], content)
            cached = st.session_state.get('gallery_result')
            if cached and cached[:2] == (kind, selected['id']):
                st.image(cached[2], width='stretch')
                st.download_button('Descargar resultado', cached[2], 'galeria.png', 'image/png')
        else:
            st.info('Tu galería está lista. Crea tu primer resultado para verlo aquí.')
    except (requests.RequestException, RuntimeError) as exc:
        st.error(str(exc))
