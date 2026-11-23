"""Source-equivalent Polars FFI plugin identity/rewrite boundary model.

Pinned OpenDP upstream main: a010591f55b1713c926f8e355091471634480307.

This models only:
  rust/src/polars/mod.rs::match_plugin and apply_plugin
  rust/src/polars/preflight/mod.rs::is_opendp_library/rebind_plugin
It does not execute Polars, OpenDP native FFI, or a third-party shared object.
The intentionally permissive behavior is an audit finding, not a fixed test.
"""
import os
import unittest


def match_plugin_library(lib: str, symbol: str, expected_symbol="noise", kwargs=b""):
    """Source translation: lib.contains('opendp'), expected symbol, small kwargs."""
    return ("opendp" in lib and symbol == expected_symbol
            and len(kwargs) <= 3)


def apply_plugin_library(lib: str, symbol="noise_plugin"):
    """Source translation: FfiPlugin { lib, .. } -> FfiPlugin { lib, symbol=KW::NAME, .. }."""
    return {"lib": lib, "symbol": symbol}


def preflight_trusted_library(lib: str):
    """Source translation: is_opendp_library only in trusted serialized-plan preflight."""
    name = os.path.basename(lib)
    return name.startswith("libopendp.") or name.startswith("opendp.")


def rebind_if_trusted_preflight_recognizes(lib: str, trusted_lib: str):
    """Source translation of trusted=true rebind_plugin for known 'noise' symbol."""
    return trusted_lib if preflight_trusted_library(lib) else lib


def untrusted_preflight_rebind_for_noise(_lib: str, trusted_lib: str):
    """Source translation: allowed noise shim in untrusted plan is always rebound."""
    return trusted_lib


class TestPolarsPluginLibraryIdentityModel(unittest.TestCase):
    def setUp(self):
        self.trusted_library = "/usr/lib/libopendp.so"
        self.third_party = "/plugins/libopendp_other.so"
        self.unrelated = "/plugins/libother.so"

    def test_third_party_path_is_accepted_as_opendp_shim(self):
        self.assertTrue(match_plugin_library(self.third_party, "noise"))
        self.assertFalse(preflight_trusted_library(self.third_party))
        self.assertFalse(match_plugin_library(self.unrelated, "noise"))
        self.assertFalse(match_plugin_library(self.third_party, "different_noise"))
        self.assertFalse(match_plugin_library(self.third_party, "noise", kwargs=b"abcd"))

    def test_private_rewrite_retains_the_noncanonical_library(self):
        self.assertTrue(match_plugin_library(self.third_party, "noise"))
        actual = apply_plugin_library(self.third_party)
        self.assertEqual(actual["lib"], self.third_party)
        self.assertEqual(actual["symbol"], "noise_plugin")
        self.assertNotEqual(actual["lib"], self.trusted_library)

    def test_trusted_preflight_does_not_rebind_but_untrusted_preflight_does(self):
        # The trusted loader preserves third-party plugins as user-controlled code.
        self.assertEqual(
            rebind_if_trusted_preflight_recognizes(self.third_party, self.trusted_library),
            self.third_party,
        )
        # The default untrusted serialized-plan loader rewrites the same shim
        # to the local trusted library, so the remote/untrusted path is protected.
        self.assertEqual(
            untrusted_preflight_rebind_for_noise(self.third_party, self.trusted_library),
            self.trusted_library,
        )

    def test_canonical_library_is_rebound_in_trusted_preflight(self):
        self.assertTrue(preflight_trusted_library("/tmp/libopendp.so"))
        self.assertEqual(
            rebind_if_trusted_preflight_recognizes("/tmp/libopendp.so", self.trusted_library),
            self.trusted_library,
        )

    def test_directory_substring_passes_matcher_but_not_canonical_preflight(self):
        ambiguous = "/tmp/opendp-not-a-library/libother.so"
        self.assertTrue(match_plugin_library(ambiguous, "noise"))
        self.assertFalse(preflight_trusted_library(ambiguous))
        self.assertEqual(apply_plugin_library(ambiguous)["lib"], ambiguous)


if __name__ == "__main__":
    unittest.main()
