"""Independent IEEE-binary32 model of OpenDP's consistent b-ary postprocessor.

This intentionally models the source arithmetic; it does not execute OpenDP Rust.
The repository test suite uses Python's standard library only.
"""

import itertools
import math
import struct
import unittest


def f32(value):
    value = float(value)
    if not math.isfinite(value):
        return value
    try:
        return struct.unpack("=f", struct.pack("=f", value))[0]
    except OverflowError:
        return math.copysign(math.inf, value)


def add(a, b):
    return f32(a + b)


def sub(a, b):
    return f32(a - b)


def mul(a, b):
    return f32(a * b)


def div(a, b):
    if b == 0:
        if a == 0 or math.isnan(a):
            return math.nan
        return math.copysign(math.inf, a)
    return f32(a / b)


def fsum(values):
    result = 0.0
    for value in values:
        result = add(result, value)
    return result


def num_nodes(layers, branching):
    return sum(branching ** i for i in range(layers))


def consistent_leaves_model(input_counts, branching):
    """Model Rust's bottom-up weighted scan, then top-down variance correction."""
    if branching < 2 or not input_counts:
        raise ValueError("invalid input")

    height = 1
    while num_nodes(height, branching) < len(input_counts):
        height += 1
    total = num_nodes(height, branching)
    omitted = total - len(input_counts)
    vars_ = [1.0] * total
    tree = [f32(v) for v in input_counts] + [0.0] * omitted

    for layer in range(height):
        zeros = omitted // branching ** (height - layer - 1)
        end = num_nodes(layer + 1, branching)
        if zeros:
            vars_[end - zeros:end] = [0.0] * zeros
            tree[end - zeros:end] = [0.0] * zeros

    for layer in reversed(range(height - 1)):
        start = num_nodes(layer, branching)
        for offset in range(branching ** layer):
            i = start + offset
            if vars_[i] == 0.0:
                continue
            children = slice(i * branching + 1, i * branching + 1 + branching)
            child_var = fsum(vars_[children])
            child_value = fsum(tree[children])
            alpha = div(1.0, vars_[i])
            vars_[i] = div(1.0, add(div(1.0, vars_[i]), div(1.0, child_var)))
            alpha = mul(alpha, vars_[i])
            tree[i] = add(mul(alpha, tree[i]), mul(sub(1.0, alpha), child_value))

    reconciled = tree[:]
    for layer in range(height - 1):
        start = num_nodes(layer, branching)
        for offset in range(branching ** layer):
            i = start + offset
            children = slice(i * branching + 1, i * branching + 1 + branching)
            child_vars = vars_[children]
            correction = sub(reconciled[i], fsum(tree[children]))
            if correction == 0.0:
                continue
            sum_var = fsum(child_vars)
            for j, child_var in zip(range(children.start, children.stop), child_vars):
                reconciled[j] = add(
                    reconciled[j], div(mul(correction, child_var), sum_var)
                )

    leaf_start = num_nodes(height - 1, branching)
    return reconciled[leaf_start:total - omitted]


class ConsistentBAryF32ModelTest(unittest.TestCase):
    def test_consistent_control(self):
        self.assertEqual(consistent_leaves_model([3, 1, 2], 2), [1.0, 2.0])

    def test_missing_leaves_controls(self):
        self.assertEqual(consistent_leaves_model([7], 2), [7.0])
        self.assertEqual(consistent_leaves_model([10, 7], 2), [8.5])
        self.assertEqual(len(consistent_leaves_model([10, 7, 0, 5], 2)), 1)
        self.assertEqual(len(consistent_leaves_model([10, 7, 0, 0, 5], 3)), 1)

    def test_i128_finite_input_overflows_to_nan_leaves(self):
        max_i128 = (1 << 127) - 1
        casted = f32(max_i128)
        self.assertTrue(math.isfinite(casted))
        self.assertTrue(math.isfinite(f32((2 * max_i128) / 3)))

        leaves = consistent_leaves_model([max_i128] * 3, 2)
        self.assertEqual(len(leaves), 2)
        self.assertTrue(all(math.isnan(v) for v in leaves))


if __name__ == "__main__":
    unittest.main()
