from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import version


class VersionTests(unittest.TestCase):
    def test_current_repository_consistency(self):
        self.assertRegex(version.current(),r'^\d+\.\d+\.\d+$')

    def test_minor_bump_and_tag_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'plugin').mkdir()
            (root/'VERSION').write_text('1.2.3\n')
            (root/'plugin/pom.xml').write_text('<project xmlns="http://maven.apache.org/POM/4.0.0"><version>1.2.3</version></project>')
            with patch.object(version,'ROOT',root),patch('sys.argv',['version.py','minor']): version.main()
            self.assertEqual((root/'VERSION').read_text().strip(),'1.3.0')
            with patch.object(version,'ROOT',root),patch('sys.argv',['version.py','check','--tag','v9.9.9']),self.assertRaises(SystemExit): version.main()
