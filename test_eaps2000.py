# test_eaps2000.py

'''
test_eaps2000.py

Author: Alexander Kozhinov <ak.alexander.kozhinov@gmail.com>
'''

from eaps2000 import eaps2k


def test_description():
    descr = eaps2k.description()
    assert 'License: Apache 2.0' in descr
