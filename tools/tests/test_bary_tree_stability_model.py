"""Independent model regression for OpenDP b-ary-tree shape and stability.

This is a Python model, not an invocation of the native OpenDP implementation.
"""

import itertools
import unittest


VALUES = (-128, -127, -1, 0, 1, 126, 127)


def saturating_add_i8(left, right):
    return max(-128, min(127, left + right))


def tree_model(values, leaf_count, branching_factor):
    assert leaf_count >= 1 and branching_factor >= 2

    leaves = 1
    height = 1
    while leaves < leaf_count:
        leaves *= branching_factor
        height += 1

    node_count = sum(branching_factor ** i for i in range(height))
    omitted = leaves - min(leaf_count, len(values))
    layers = [list(values[:leaf_count]) + [0] * omitted]

    for _ in range(height - 1):
        previous = layers[-1]
        next_layer = []
        for start in range(0, len(previous), branching_factor):
            total = 0
            for v in previous[start:start + branching_factor]:
                total = saturating_add_i8(total, v)
            next_layer.append(total)
        layers.append(next_layer)

    output = list(itertools.chain.from_iterable(reversed(layers)))
    return output[:node_count - omitted], height, node_count - omitted


class TestBAryTreeStabilityModel(unittest.TestCase):
    def test_shape_and_single_coordinate_stability(self):
        checked = 0
        for leaf_count in range(1, 6):
            for b in range(2, 5):
                for n in range(min(leaf_count + 2, 3) + 1):
                    for x in itertools.product(VALUES, repeat=n):
                        base, h, expected_length = tree_model(x, leaf_count, b)
                        self.assertEqual(len(base), expected_length)

                        for i in range(n):
                            for replacement in VALUES:
                                if replacement == x[i]:
                                    continue
                                y = x[:i] + (replacement,) + x[i + 1:]
                                result, _, _ = tree_model(y, leaf_count, b)
                                self.assertEqual(len(result), expected_length)
                                delta = [a - b for a, b in zip(base, result)]
                                input_change = abs(x[i] - replacement)
                                self.assertLessEqual(sum(abs(z) for z in delta), h * input_change)
                                self.assertLessEqual(
                                    sum(z * z for z in delta),
                                    h * input_change * input_change,
                                )
                                checked += 1

        self.assertEqual(checked, 102060)


if __name__ == "__main__":
    unittest.main()
