#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    test_static_file

    Test the static file feature of nereid

    :copyright: (c) 2013-2014 by Openlabs Technologies & Consulting (P) LTD
    :license: BSD, see LICENSE for more details.
"""
import os
import time
import unittest
import cStringIO
from io import BytesIO
from pytz import timezone
from urllib import unquote
from datetime import datetime

import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, USER, DB_NAME, CONTEXT
from trytond.transaction import Transaction
from trytond.config import CONFIG
from nereid.testing import NereidTestCase
from nereid import render_template
from PIL import Image

CONFIG['smtp_server'] = 'smtpserver'
CONFIG['smtp_user'] = 'test@xyz.com'
CONFIG['smtp_password'] = 'testpassword'
CONFIG['smtp_port'] = 587
CONFIG['smtp_tls'] = True
CONFIG['smtp_from'] = 'from@xyz.com'
CONFIG.options['data_path'] = '/tmp/temp_tryton_data/'


class TestStaticFile(NereidTestCase):

    def setUp(self):
        trytond.tests.test_tryton.install_module('nereid_image_transformation')

        self.nereid_website_obj = POOL.get('nereid.website')
        self.nereid_user_obj = POOL.get('nereid.user')
        self.url_map_obj = POOL.get('nereid.url_map')
        self.company_obj = POOL.get('company.company')
        self.currency_obj = POOL.get('currency.currency')
        self.language_obj = POOL.get('ir.lang')
        self.country_obj = POOL.get('country.country')
        self.subdivision_obj = POOL.get('country.subdivision')
        self.party_obj = POOL.get('party.party')
        self.address_obj = POOL.get('party.address')
        self.contact_mech_obj = POOL.get('party.contact_mechanism')
        self.static_file_obj = POOL.get('nereid.static.file')
        self.static_folder_obj = POOL.get('nereid.static.folder')
        self.nereid_website_locale_obj = POOL.get('nereid.website.locale')

    def setup_defaults(self):
        """
        Setup the defaults
        """
        usd, = self.currency_obj.create([{
            'name': 'US Dollar',
            'code': 'USD',
            'symbol': '$',
        }])
        self.party, = self.party_obj.create([{
            'name': 'Openlabs',
        }])
        self.company, = self.company_obj.create([{
            'party': self.party,
            'currency': usd,
        }])
        self.guest_party, = self.party_obj.create([{
            'name': 'Guest User',
        }])
        self.guest_user, = self.nereid_user_obj.create([{
            'party': self.guest_party,
            'display_name': 'Guest User',
            'email': 'guest@openlabs.co.in',
            'password': 'password',
            'company': self.company.id,
        }])

        registered_user_party, = \
            self.party_obj.create([{'name': 'Registered User'}])
        self.registered_user, = self.nereid_user_obj.create([{
            'party': registered_user_party.id,
            'display_name': 'Registered User',
            'email': 'email@example.com',
            'password': 'password',
            'company': self.company.id,
        }])

        url_map_id, = self.url_map_obj.search([], limit=1)
        en_us, = self.language_obj.search([('code', '=', 'en_US')])
        currency, = self.currency_obj.search([('code', '=', 'USD')])
        locale, = self.nereid_website_locale_obj.create([{
            'code': 'en_US',
            'language': en_us,
            'currency': currency,
        }])
        self.nereid_website_obj.create([{
            'name': 'localhost',
            'url_map': url_map_id,
            'company': self.company,
            'application_user': USER,
            'default_locale': locale,
            'guest_user': self.guest_user,
        }])
        self.templates = {
            'home.jinja':
                '''
                {% set static_file = static_file_obj(static_file_id) %}
                {{ static_file.transform_command().thumbnail(120, 120).resize(
                    100, 100) }}
                ''',
        }

    def create_static_file(self, file_buffer):
        """
        Creates the static file for testing
        """
        folder, = self.static_folder_obj.create([{
            'folder_name': 'test',
            'description': 'Test Folder'
        }])

        return self.static_file_obj.create([{
            'name': 'test.png',
            'folder': folder.id,
            'file_binary': file_buffer,
        }])[0]

    def test_0010_static_file_url(self):
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()

            file_buffer = buffer('test-content')
            file = self.create_static_file(file_buffer)
            self.assertFalse(file.url)

            app = self.get_app()
            static_file_obj = self.static_file_obj

            with app.test_request_context('/'):
                rv = render_template(
                    'home.jinja',
                    static_file_obj=static_file_obj,
                    static_file_id=file.id,
                )
                self.assertTrue(
                    '/static-file-transform/1/'
                    'thumbnail,w_120,h_120,m_n/'
                    'resize,w_100,h_100,m_n.png'
                    in unquote(unicode(rv))
                )

    def test_0020_transform_static_file(self):
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()

            img_file = BytesIO()
            img = Image.new("RGB", (100, 100), "white")
            img.save(img_file, 'png')

            img_file.seek(0)
            file = self.create_static_file(buffer(img_file.read()))

            self.assertFalse(file.url)

            app = self.get_app()

            with app.test_client() as c:
                rv = c.get(
                    '/static-file-transform/%d/thumbnail,w_120,h_120,m_n/'
                    'resize,w_100,h_100,m_n.png' % file.id
                )
                self.assertEqual(rv.status_code, 200)
                img = Image.open(cStringIO.StringIO(rv.data))
                # Assert if white
                self.assertEqual(img.getpixel((0, 0)), (255, 255, 255))

            # Save temp image file datetime
            temp_image_time = datetime.fromtimestamp(os.path.getmtime(
                '/tmp/nereid/%s/%d/'
                'thumbnailw_120h_120m_n_resizew_100h_100m_n.png' %
                (DB_NAME, file.id)
            ), timezone('UTC'))
            Transaction().cursor.commit()  # Commit to retain file

        time.sleep(1)

        with Transaction().start(DB_NAME, USER, CONTEXT):
            # Access file again
            with app.test_client() as c:
                rv = c.get(
                    '/static-file-transform/%d/thumbnail,w_120,h_120,m_n/'
                    'resize,w_100,h_100,m_n.png' % file.id
                )
                self.assertEqual(rv.status_code, 200)
                img = Image.open(cStringIO.StringIO(rv.data))
                # Assert if white
                self.assertEqual(img.getpixel((0, 0)), (255, 255, 255))

            # Assert if file is not modified.
            self.assertEqual(
                temp_image_time, datetime.fromtimestamp(os.path.getmtime(
                    '/tmp/nereid/%s/%d/'
                    'thumbnailw_120h_120m_n_resizew_100h_100m_n.png' %
                    (DB_NAME, file.id)
                ), timezone('UTC'))
            )

            # Generate new image
            img_file = BytesIO()
            img = Image.new("RGB", (100, 100), "black")
            img.save(img_file, 'png')

            img_file.seek(0)

            # Update image in same file
            file = self.static_file_obj(file.id)
            file.file_binary = img_file.read()
            file.save()

            app = self.get_app()

            with app.test_client() as c:
                rv = c.get(
                    '/static-file-transform/%d/thumbnail,w_120,h_120,m_n/'
                    'resize,w_100,h_100,m_n.png' % file.id
                )
                self.assertEqual(rv.status_code, 200)
                img = Image.open(cStringIO.StringIO(rv.data))
                # Assert if black
                self.assertEqual(img.getpixel((0, 0)), (0, 0, 0))

            # Assert if image is updated
            self.assertTrue(
                temp_image_time < datetime.fromtimestamp(os.path.getmtime(
                    '/tmp/nereid/%s/%d/'
                    'thumbnailw_120h_120m_n_resizew_100h_100m_n.png' %
                    (DB_NAME, file.id)
                ), timezone('UTC'))
            )


def suite():
    "Nereid test suite"
    test_suite = unittest.TestSuite()
    test_suite.addTests(
        unittest.TestLoader().loadTestsFromTestCase(TestStaticFile)
    )
    return test_suite


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
