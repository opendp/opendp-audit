"""CI-only replacement of the exact metric-cast closure in pinned OpenDP.

Do not apply this patch to upstream: it is an experimental repair hypothesis,
used solely in the ephemeral GitHub Actions checkout for audit issue #27.
"""

import pathlib
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_metric_unbounded_checked.py UPSTREAM_CAST_METRIC_MOD_RS")

path = pathlib.Path(sys.argv[1])
source = path.read_text()
original = "        StabilityMap::new(|d_in| d_in * 2),"
replacement = "        StabilityMap::new_from_constant(2),"

if source.count(original) != 1:
    raise SystemExit("expected exactly one original metric-cast map; pinned source changed")

path.write_text(source.replace(original, replacement, 1))
print("Replaced the pinned metric-cast stability map with a fallible constant map (CI checkout only)")
