"""Compile the pinned upstream R tuple decoders with test-only R API stubs.

This runs the *unaltered* decoder function bodies saved in the adjacent C
fixture. It does not link R or OpenDP, so it is a dispatch witness rather than
an R integration test. The fixture corresponds to upstream
ef1a238634d6196b01a1a1e77d3d5ad2340e3094.
"""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class TestRFFINestedTupleDispatch(unittest.TestCase):
    def test_pinned_c_decoder_dispatch(self):
        compiler = shutil.which("cc")
        if compiler is None:
            self.skipTest("C compiler not installed")

        src = Path(__file__).with_name("r_ffi_nested_tuple_dispatch.c")
        with tempfile.TemporaryDirectory() as tempdir:
            program = Path(tempdir) / "r_ffi_nested_tuple_dispatch"
            compile_result = subprocess.run(
                [compiler, "-std=c11", "-O0", "-Wall", "-Wextra",
                 str(src), "-o", str(program)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)

            result = subprocess.run(
                [str(program)], capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("OK primitive_tuple\n", result.stdout)
            self.assertIn(
                "EXPECTED_ERROR privacy_profile_tuple: "
                "voidptr_to_sexp unknown type: PrivacyProfile\n", result.stdout,
            )
            self.assertIn(
                "EXPECTED_ERROR private_candidate_some: "
                "voidptr_to_sexp unknown type: AnyObject\n", result.stdout,
            )
            self.assertIn("OK private_candidate_none\n", result.stdout)


if __name__ == "__main__":
    unittest.main()
