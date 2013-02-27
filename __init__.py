'''

An image manipulation extension for nereid static files

:copyright: (c) 2013 by Openlabs Technologies & Consulting (P) Limited.
:license: GPLv3, see LICENSE for more details
'''
from trytond.pool import Pool
from .static_file import *

def register():
    Pool.register(
        NereidStaticFile,
        module='nereid_image_transformation', type_='model')
