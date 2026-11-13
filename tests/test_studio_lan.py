import unittest
from creator_tools import studio

class LanTests(unittest.TestCase):
    def test_explicit_lan_host_is_allowed(self):
        self.assertTrue(hasattr(studio,'allowed_hosts'),'LAN binding helper missing')
        self.assertIn('192.168.1.20:4318',studio.allowed_hosts('192.168.1.20',4318))
        self.assertNotIn('evil.example:4318',studio.allowed_hosts('192.168.1.20',4318))
    def test_default_remains_loopback(self):
        self.assertTrue(hasattr(studio,'allowed_hosts'),'LAN binding helper missing')
        self.assertEqual(studio.allowed_hosts('127.0.0.1',4318),{'127.0.0.1:4318','localhost:4318'})
    def test_public_and_wildcard_binds_rejected(self):
        self.assertTrue(hasattr(studio,'allowed_hosts'),'LAN binding helper missing')
        for host in ['0.0.0.0','8.8.8.8','example.com','::','169.254.169.254']:
            with self.assertRaises(ValueError):studio.allowed_hosts(host,4318)

if __name__=='__main__':unittest.main()
