from unittest import TestCase
import helper

class TestHelper(TestCase):

    def test_truthy(self):

        # Test true statements
        for value in { 'yes', 'y', 'Y', 'YES', 'true', True, 'TRUE', 'on', 'On', 'ON', '1', 1 }:
            self.assertTrue(helper.truthy(value), value)

        # Test false statements
        for value in { 'no', 'n', 'N', 'NO', 'false', False, 'FALSE', 'off', 'Off', 'OFF', '0', 0 }:
            self.assertFalse(helper.truthy(value))
