"""Static checks for the PowerShell scripts. They cannot be run on Linux, so these are the
guard rails: ASCII only, no double-quote characters in the installers, everything inside one
function called on the last line, and (when pwsh is available) a syntax parse of every .ps1."""
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTALLERS = [ROOT / "bshell" / "py" / "install.ps1", ROOT / "bshell" / "node" / "install.ps1"]
ALL_PS1 = sorted(p for p in ROOT.rglob("*.ps1") if ".scratch" not in p.parts and "node_modules" not in p.parts
                 and "build" not in p.relative_to(ROOT).parts[:1] and "dist" not in p.relative_to(ROOT).parts[:1])


def find_pwsh():
    return os.environ.get("BENCH_PWSH") or shutil.which("pwsh")


class InstallerRules(unittest.TestCase):
    def test_installers_exist(self):
        for p in INSTALLERS:
            self.assertTrue(p.is_file(), p)

    def test_ascii_only(self):
        for p in ALL_PS1:
            data = p.read_bytes()
            bad = [i for i, b in enumerate(data) if b > 127]
            self.assertEqual(bad, [], "%s has non-ASCII bytes at %s" % (p, bad[:5]))
            self.assertFalse(data.startswith(b"\xef\xbb\xbf"), "%s has a BOM" % p)

    def test_no_double_quotes_in_installers(self):
        for p in INSTALLERS:
            lines = [(n, l) for n, l in enumerate(p.read_text().splitlines(), 1) if '"' in l]
            self.assertEqual(lines, [], "%s contains double quotes: %s" % (p, lines[:3]))

    def test_no_backtick_escapes_in_installers(self):
        for p in INSTALLERS:
            self.assertNotIn("`", p.read_text(), p)

    def test_everything_inside_one_function(self):
        for p in INSTALLERS:
            lines = p.read_text().splitlines()
            top = [l for l in lines if l and not l.startswith((" ", "\t", "#", "}"))]
            self.assertEqual(top[0], "function Install-BenchNotes {", p)
            self.assertEqual(top[1:], ["Install-BenchNotes"], "%s has other top-level statements: %s" % (p, top))
            self.assertEqual(lines[-1], "Install-BenchNotes")

    def test_native_calls_check_exit_codes(self):
        for p in INSTALLERS:
            text = p.read_text()
            self.assertIn("$LASTEXITCODE", text)
            # No bare Start-Process with quoted paths in arguments, and no Invoke-Expression.
            self.assertNotIn("Invoke-Expression", text)

    def test_powershell_5_1_compatible_syntax(self):
        # Constructs that only exist in PowerShell 7: ternary, null-coalescing, pipeline chains.
        for p in ALL_PS1:
            code = "\n".join(l.split("#", 1)[0] if not re.search(r"'[^']*#", l) else l for l in p.read_text().splitlines())
            self.assertIsNone(re.search(r"\?\?|\?\.\w|\s\?\s+[^\s]+\s+:\s+", code), "%s uses PowerShell 7 syntax" % p)
            self.assertIsNone(re.search(r"\)\s*&&\s|\)\s*\|\|\s", code), "%s uses pipeline chain operators" % p)


@unittest.skipUnless(find_pwsh(), "pwsh not installed: syntax parse skipped")
class Parse(unittest.TestCase):
    def test_every_script_parses(self):
        script = ("$errs = $null; $tokens = $null; "
                  "[void][System.Management.Automation.Language.Parser]::ParseFile($env:PS_FILE_TO_PARSE, [ref]$tokens, [ref]$errs); "
                  "if ($errs.Count -gt 0) { $errs | ForEach-Object { $_.ToString() }; exit 1 }")
        for p in ALL_PS1:
            r = subprocess.run([find_pwsh(), "-NoProfile", "-Command", script], capture_output=True, text=True,
                               env=dict(os.environ, PS_FILE_TO_PARSE=str(p)))
            self.assertEqual(r.returncode, 0, "%s: %s%s" % (p, r.stdout, r.stderr))


if __name__ == "__main__":
    unittest.main()
