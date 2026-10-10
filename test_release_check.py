"""2.9.100: release discipline and code health, checked on every push (Linux and Windows)."""
import re
import unittest
from pathlib import Path

import release_check

ROOT = Path(__file__).resolve().parent
# Code-health ratchet: these numbers may only go DOWN. Lower them when screens are tidied.
MAX_LINES_OVER_200 = 106  # 2.9.102: 505 -> 106
STAR_IMPORT_FILES = set()  # 2.9.102: none left (there were 26)


class ReleaseCheckTest(unittest.TestCase):
    def test_repository_is_ready_to_release(self):
        self.assertEqual(release_check.problems(), [])

    def test_long_lines_do_not_grow(self):
        count = sum(1 for f in ROOT.glob("*.py") for line in f.read_text(encoding="utf-8").splitlines() if len(line) > 200)
        self.assertLessEqual(count, MAX_LINES_OVER_200, "new lines longer than 200 characters - split them")

    def test_no_new_star_imports(self):
        found = {f.name for f in ROOT.glob("*.py") if re.search(r"^from \S+ import \*", f.read_text(encoding="utf-8"), re.M)}
        self.assertEqual(found - STAR_IMPORT_FILES, set(), "new 'from x import *' - import the names you use")


if __name__ == "__main__":
    unittest.main()
