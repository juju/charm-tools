from __future__ import print_function

from unittest import TestCase
from charmtools import utils
from six import StringIO


class TestUtils(TestCase):

    def test_delta_python(self):
        a = StringIO("""
        def foo(n):
            return n * 2


        @when('db.ready')
        def react(db):
            print(db)
        """)

        b = StringIO("""
        def foo(n):
            return n * 2


        @when('db.ready', 'bar')
        def react(db):
            print(db)
        """)

        result = StringIO()
        t = utils.TermWriter(fp=result)
        rc = utils.delta_python_dump(a, b, utils.REACTIVE_PATTERNS,
                                     context=3,
                                     term=t,
                                     from_name="Alpha",
                                     to_name="Beta")
        # return code here indicates that there was a diff
        self.assertFalse(rc)
        result.seek(0)
        output = result.read()
        self.assertIn("Alpha", output)
        self.assertIn("Beta", output)
        self.assertIn("@when('db.ready'", output)
        self.assertIn("bar", output)
