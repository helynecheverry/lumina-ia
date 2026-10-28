"""Native frontend regression checks against the running local proxy and API."""
import sys
import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]

class FrontendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright=sync_playwright().start()
        cls.browser=cls.playwright.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.playwright.stop()
    def setUp(self):
        self.page=self.browser.new_page(viewport={'width':1440,'height':1000})
        self.errors=[];self.page.on('pageerror',lambda error:self.errors.append(str(error)))
    def tearDown(self):
        self.page.close();self.assertEqual(self.errors,[])
    def studio(self):
        self.page.goto('http://127.0.0.1:8501/studio?view=explore')
        self.page.locator('#style-count').get_by_text('32',exact=True).wait_for()
        for control in ('#model-select','#character-options','#style-options'):
            self.page.locator(control).evaluate("el=>el.closest('details').open=true")
    def discovery(self):
        self.page.goto('http://127.0.0.1:8501/studio?view=discovery')
        self.page.locator('#discovery-catalog button').first.wait_for(state='attached')
        self.page.locator('.discovery-manual > summary').click()

    def test_home_and_mobile_navigation_expose_both_experiences(self):
        self.page.set_viewport_size({'width':390,'height':844})
        self.page.goto('http://127.0.0.1:8501/')
        self.page.locator('.experience-card').first.wait_for()
        self.assertEqual(self.page.locator('.experience-card').count(),2)
        for label in ('Pokémon','Versión joven','Estudio','Galería'):
            self.assertTrue(self.page.get_by_role('navigation',name='Secciones').get_by_role('link',name=label,exact=True).is_visible())
        self.page.locator('.youth-experience').click()
        self.page.locator('#youth-view').wait_for(state='visible')
        self.assertEqual(self.page.locator('#youth-tab').get_attribute('aria-current'),'page')
        self.page.locator('#discovery-tab').click()
        self.page.locator('#discovery-view').wait_for(state='visible')
        self.assertEqual(self.page.locator('#discovery-tab').get_attribute('aria-current'),'page')
        self.page.go_back()
        self.page.locator('#youth-view').wait_for(state='visible')
        self.page.locator('#explore-tab').click()
        self.page.locator('#explore-view').wait_for(state='visible')
        self.assertEqual(self.page.evaluate('document.documentElement.scrollWidth'),390)

    def test_experience_navigation_remains_visible_without_backend(self):
        self.page.route('**/api/influencer/config',lambda route:route.fulfill(status=503,content_type='application/json',body='{"detail":"Motor desconectado"}'))
        self.page.goto('http://127.0.0.1:8501/')
        self.assertTrue(self.page.locator('.pokemon-experience').is_visible())
        self.page.locator('#youth-tab').click()
        self.page.locator('#youth-view').wait_for(state='visible')
        self.assertTrue(self.page.locator('#youth-generate').is_disabled())
        self.page.locator('#discovery-tab').click()
        self.page.locator('#discovery-view').wait_for(state='visible')

    def test_youth_upload_age_and_generation_form(self):
        submitted=[]
        def capture(route):
            submitted.append(route.request.post_data_buffer.decode('latin1'))
            route.fulfill(status=400,content_type='application/json',body='{"detail":"Youth form checked"}')
        self.page.route('**/api/influencer/generations',capture)
        self.page.set_viewport_size({'width':390,'height':844})
        self.page.goto('http://127.0.0.1:8501/studio?view=youth')
        self.page.locator('#youth-view').wait_for(state='visible')
        self.assertTrue(self.page.locator('#youth-generate').is_disabled())
        self.page.locator('#reference-input').set_input_files(str(ROOT/'web/assets/demo-reference.png'))
        self.assertTrue(self.page.locator('#youth-view').is_visible())
        self.assertTrue(self.page.locator('#youth-photo').is_visible())
        self.page.locator('#youth-age').select_option('10')
        self.page.locator('#youth-generate').click()
        self.page.locator('#toast').get_by_text('Youth form checked',exact=True).wait_for()
        self.assertEqual(len(submitted),1)
        self.assertIn('name="target_age"\r\n\r\n10',submitted[0])
        self.assertNotIn('name="inspiration_id"',submitted[0])
        self.assertEqual(self.page.evaluate('document.documentElement.scrollWidth'),390)
        self.page.locator('#youth-clear').click()
        self.assertTrue(self.page.locator('#youth-generate').is_disabled())
        self.assertFalse(self.page.locator('#youth-photo').is_visible())

    def test_discovery_categories_search_and_mobile_layout(self):
        self.page.set_viewport_size({'width':390,'height':844})
        self.discovery()
        self.assertEqual(self.page.locator('#discovery-catalog button').count(),16)
        self.page.locator('[data-universe="digimon"]').click()
        self.assertEqual(self.page.locator('#discovery-catalog button').count(),12)
        self.page.locator('#discovery-search').fill('Agumon')
        self.assertEqual(self.page.locator('#discovery-catalog button').count(),1)
        self.page.locator('[data-universe="zodiac"]').click()
        self.assertEqual(self.page.locator('#discovery-catalog button').count(),12)
        self.assertIn('no determina',self.page.locator('#discovery-category-description').inner_text())
        self.page.get_by_role('button',name='Elegir Aries',exact=True).click()
        self.assertTrue(self.page.locator('.optional-transformation').is_visible())
        self.assertEqual(self.page.evaluate('document.documentElement.scrollWidth'),390)

    def test_discovery_new_photo_clears_previous_affinity(self):
        self.discovery()
        self.page.locator('#reference-input').set_input_files(str(ROOT/'web/assets/demo-reference.png'))
        self.assertTrue(self.page.locator('#discovery-view').is_visible())
        self.page.get_by_role('button',name='Elegir Pikachu',exact=True).click()
        self.assertTrue(self.page.locator('#discovery-selected').is_visible())
        self.page.locator('#reference-input').set_input_files(str(ROOT/'web/assets/demo-reference.jpg'))
        self.assertFalse(self.page.locator('#discovery-selected').is_visible())
        self.assertEqual(self.page.evaluate('discovery.matches.length'),0)
        self.page.locator('#discovery-clear').click()
        self.assertTrue(self.page.locator('#discovery-analyze').is_disabled())

    def test_discovery_assigns_character_without_generating_or_replacing_photo(self):
        import json
        from app.discovery_catalog import public_catalog
        item=next(item for item in public_catalog()['pokemon']['items'] if item['id']=='pokemon:pikachu')
        generations=[]
        self.page.route('**/api/influencer/generations',lambda route:(generations.append(route.request.url),route.abort()))
        self.page.route('**/api/influencer/discovery/match',lambda route:route.fulfill(content_type='application/json',body=json.dumps(dict(assigned_character=item,suggestions=[dict(item,rank=1)],photo_modified=False))))
        self.discovery()
        self.page.locator('#reference-input').set_input_files(str(ROOT/'web/assets/demo-reference.png'))
        original=self.page.locator('#discovery-photo').get_attribute('src')
        self.page.locator('#discovery-analyze').click()
        self.page.wait_for_function("discovery.selected === 'pokemon:pikachu'")
        self.assertIn('Pikachu',self.page.locator('#discovery-selected-name').inner_text())
        self.assertEqual(self.page.locator('#discovery-photo').get_attribute('src'),original)
        self.assertTrue(self.page.locator('#discovery-view').is_visible())
        self.assertEqual(generations,[])

    def test_discovery_selected_target_is_sent_to_generation(self):
        submitted=[]
        def capture(route):
            submitted.append(route.request.post_data_buffer.decode('latin1'))
            route.fulfill(status=400,content_type='application/json',body='{"detail":"Prueba de formulario; sin generación GPU"}')
        self.page.route('**/api/influencer/generations',capture)
        self.discovery()
        self.page.locator('#reference-input').set_input_files(str(ROOT/'web/assets/demo-reference.png'))
        self.page.get_by_role('button',name='Elegir Pikachu',exact=True).click()
        self.page.locator('.optional-transformation > summary').click()
        self.page.locator('#discovery-finish').select_option('three_d')
        self.page.locator('#discovery-transform').click()
        self.page.locator('#toast').get_by_text('Prueba de formulario; sin generación GPU',exact=True).wait_for()
        self.assertEqual(len(submitted),1)
        self.assertIn('name="inspiration_id"',submitted[0])
        self.assertIn('pokemon:pikachu',submitted[0])
        self.assertIn('three_d',submitted[0])
        self.assertTrue(self.page.locator('#explore-view').is_visible())

    def test_discovery_history_restores_named_target(self):
        import requests
        jobs=requests.get('http://127.0.0.1:8000/history?kind=generations&limit=50').json()
        job=next((job for job in jobs if job['status']=='completed' and job.get('inspiration_id')),None)
        if not job:self.skipTest('Requiere una transformación nombrada completada')
        self.page.goto('http://127.0.0.1:8501/studio?creation='+job['id'])
        self.page.wait_for_function('id => state.inspirationId === id',arg=job['inspiration_id'])
        self.assertIn(job['inspiration_name'],self.page.locator('#selection-summary').inner_text())

    def test_uploaded_reference_replaces_examples_and_old_result(self):
        self.studio()
        self.page.locator('#reference-input').set_input_files(str(ROOT/'web/assets/demo-reference.jpg'))
        self.assertTrue(self.page.locator('#active-reference').is_visible())
        self.assertFalse(self.page.locator('#portrait-fan').is_visible())
        self.assertIn('próxima creación',self.page.locator('#reference-context').inner_text())
        self.page.evaluate("document.querySelector('#result-image').hidden=false; showView('result')")
        self.page.locator('#reference-input').set_input_files({'name':'otra-foto.jpg','mimeType':'image/jpeg','buffer':(ROOT/'web/assets/demo-reference.jpg').read_bytes()})
        self.assertFalse(self.page.locator('#result-image').is_visible())
        self.assertTrue(self.page.locator('#explore-view').is_visible())
        self.assertEqual(self.page.locator('#active-reference-image').get_attribute('src'),self.page.locator('#reference-preview').get_attribute('src'))
        self.page.locator('#reference-clear').click()
        self.assertFalse(self.page.locator('#active-reference').is_visible())
        self.assertFalse(self.page.locator('#portrait-fan').is_visible())

    def test_slow_history_reference_cannot_replace_new_upload(self):
        import requests
        jobs=requests.get('http://127.0.0.1:8000/history?kind=generations&limit=50').json()
        job=next(job for job in jobs if job['status']=='completed')
        pending=[]
        self.page.route('**/api/influencer/generations/'+job['id']+'/reference',lambda route:pending.append(route))
        self.page.goto('http://127.0.0.1:8501/studio?creation='+job['id'])
        for attempt in range(100):
            if pending:break
            self.page.wait_for_timeout(50)
        self.assertTrue(pending)
        self.page.locator('#reference-input').set_input_files({'name':'nueva-referencia.jpg','mimeType':'image/jpeg','buffer':(ROOT/'web/assets/demo-reference.jpg').read_bytes()})
        selected=self.page.locator('#reference-preview').get_attribute('src')
        pending[0].fulfill(status=200,content_type='image/jpeg',body=(ROOT/'web/assets/demo-reference.jpg').read_bytes())
        self.page.wait_for_timeout(300)
        self.assertEqual(self.page.locator('#reference-label').inner_text(),'nueva-referencia.jpg')
        self.assertEqual(self.page.locator('#reference-preview').get_attribute('src'),selected)
        self.assertTrue(self.page.locator('#explore-view').is_visible())

    def test_slow_result_cannot_reappear_after_new_upload(self):
        import requests
        jobs=requests.get('http://127.0.0.1:8000/history?kind=generations&limit=50').json()
        job=next(job for job in jobs if job['status']=='completed')
        pending=[]
        self.page.route('**/api/image/'+job['id']+'?kind=generations',lambda route:pending.append(route))
        self.page.goto('http://127.0.0.1:8501/studio?creation='+job['id'])
        for attempt in range(100):
            if pending:break
            self.page.wait_for_timeout(50)
        self.assertTrue(pending)
        self.page.locator('#reference-input').set_input_files(str(ROOT/'web/assets/demo-reference.jpg'))
        pending[0].fulfill(status=200,content_type='image/jpeg',body=(ROOT/'web/assets/demo-reference.jpg').read_bytes())
        self.page.wait_for_timeout(300)
        self.assertFalse(self.page.locator('#result-image').is_visible())
        self.assertIsNone(self.page.evaluate('state.resultBlob'))
        self.assertTrue(self.page.locator('#explore-view').is_visible())

    def test_hybrid_prefers_editing_model_and_preserves_uploaded_reference(self):
        self.studio()
        self.page.locator('#reference-input').set_input_files(str(ROOT/'web/assets/demo-reference.jpg'))
        reference=self.page.locator('#reference-preview').get_attribute('src')
        self.page.locator('#model-select').select_option('portrait_sd15')
        self.page.locator('[data-personality="fox"]').click()
        self.assertEqual(self.page.locator('#model-select').input_value(),'flux_klein')
        self.assertEqual(self.page.locator('#reference-preview').get_attribute('src'),reference)
        self.assertTrue(self.page.locator('#identity').is_disabled())
        self.assertTrue(self.page.locator('#generate').is_enabled())

    def test_landing_links_to_creative_studio(self):
        self.page.goto('http://127.0.0.1:8501')
        self.page.get_by_role('heading',name='¿Qué quieres descubrir?',exact=True).wait_for()
        self.assertEqual(self.page.locator('.experience-card').count(),2)
        self.page.get_by_role('link',name='Abrir el estudio creativo',exact=False).click()
        self.page.locator('#explore-view').wait_for(state='visible')
        self.page.locator('#style-options button').first.wait_for(state='attached')
        self.assertEqual(self.page.locator('#style-options button').count(),32)

    def test_character_survives_reload_and_preview(self):
        self.studio()
        self.page.locator('[data-personality="bold"]').click()
        self.page.reload()
        self.page.locator('[data-personality="bold"][aria-pressed="true"]').wait_for(state='attached')
        self.page.get_by_role('button',name='Ver instrucciones ↗',exact=True).click()
        self.page.locator('#prompt-preview').wait_for(state='visible')
        self.assertIn('avant-garde',self.page.locator('#prompt-preview').inner_text())
        self.page.locator('#character-options').evaluate("el=>el.closest('details').open=true")
        self.assertIn('Atrevido',self.page.locator('#character-description').inner_text())

    def test_styles_filters_and_personal_prompt(self):
        self.studio()
        self.page.locator('[data-personality="bold"]').click()
        self.page.get_by_role('textbox',name='Buscar estilo').fill('pirata')
        self.assertEqual(self.page.locator('#style-options button').count(),1)
        self.page.get_by_role('button',name='Capitán pirata',exact=True).click()
        self.assertEqual(self.page.locator('#identity').input_value(),'0.6')
        self.page.get_by_role('textbox',name='Buscar estilo').fill('')
        self.page.get_by_role('button',name='Editorial de moda',exact=True).click()
        self.page.get_by_role('textbox',name='Describe tu transformación',exact=True).fill('Llevo una chaqueta roja')
        self.page.get_by_role('button',name='Ver instrucciones ↗',exact=True).click()
        self.page.locator('#prompt-preview').wait_for(state='visible',timeout=45000)
        self.assertIn('red',self.page.locator('#prompt-preview').inner_text().lower())
        self.assertNotIn('designer jacket',self.page.locator('#prompt-preview').inner_text())

    def test_model_resolution_and_resource_availability(self):
        self.studio()
        self.page.wait_for_function("document.querySelector('#model-select').options.length===4")
        self.page.locator('#model-select').select_option('portrait_sdxl')
        self.page.locator('#framing').select_option('portrait')
        self.assertIn('768 × 1024',self.page.locator('#model-resolution').inner_text())
        self.assertIsNotNone(self.page.locator('#model-select option[value="qwen_edit"]').get_attribute('disabled'))
        self.page.reload()
        self.page.wait_for_function("document.querySelector('#model-select').value==='portrait_sdxl'")

    def test_every_appearance_section_applies_and_character_catalog_is_dynamic(self):
        self.studio()
        self.assertGreaterEqual(self.page.locator('[data-personality]').count(),10)
        self.page.locator('[data-personality="cyborg"]').click()
        selections={'presentation':'masculine','outfit':'red_jacket','scene':'blue_studio','lighting':'dramatic'}
        for key,value in selections.items():
            group=self.page.locator('#'+key).locator('..')
            group.locator('summary').click()
            choice=self.page.locator('[data-appearance-group="'+key+'"][data-appearance-value="'+value+'"]')
            self.assertTrue(choice.is_visible())
            choice.click()
            self.assertEqual(choice.get_attribute('aria-pressed'),'true')
        self.assertIn('Chaqueta roja',self.page.locator('#selection-summary').inner_text())
        self.assertIn('Fondo azul',self.page.locator('#scene-summary').inner_text())
        self.page.locator('#preview-prompt').click()
        self.page.locator('#prompt-preview').wait_for(state='visible')
        text=self.page.locator('#prompt-preview').inner_text()
        for expected in ['red jacket','plain blue studio background','dramatic cinematic lighting','masculine presentation','cyborg']:
            self.assertIn(expected,text)
    def test_upload_and_mobile_controls(self):
        self.page.set_viewport_size({'width':390,'height':844})
        self.studio()
        self.page.get_by_role('button',name='Abrir configuración').click()
        self.page.locator('#reference-input').set_input_files(str(ROOT/'artifacts/local-influencer/reference.png'))
        self.assertTrue(self.page.get_by_role('button',name='Generar',exact=True).is_enabled())
        self.page.get_by_role('button',name='Cerrar configuración').click()
        self.assertFalse(self.page.locator('.builder').evaluate("el=>el.classList.contains('mobile-open')"))
        self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),390)
    def test_gallery_and_tools(self):
        self.studio()
        self.page.locator('#history-tab').click()
        self.page.locator('.history-copy').first.wait_for()
        self.page.locator('#explore-tab').click()
        self.page.locator('#tools-mode').click()
        self.page.get_by_role('heading',name='Editor de imagen',exact=True).wait_for()
        self.page.locator('#tool-input').set_input_files(str(ROOT/'artifacts/local-influencer/reference.png'))
        self.page.locator('#brightness').fill('15')
        self.page.get_by_role('button',name='Aplicar y guardar',exact=True).click()
        self.page.locator('#tool-download').wait_for(state='visible',timeout=30000)

if __name__=='__main__':unittest.main()
