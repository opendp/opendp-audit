"""Exact probability law implied by OpenDP's pinned Bernoulli float bit decoder.

The model assumes an unbiased random bit stream with first-head index
Pr[i] = 2**(-i-1); no OpenDP Rust code or entropy implementation is run.
"""
from fractions import Fraction
import random
import struct
import unittest


def binary_float(raw, bits):
    return struct.unpack(">f" if bits == 32 else ">d",
                         raw.to_bytes(bits // 8, "big"))[0]


def implied_success_probability(raw, bits):
    """Replicate the first-head-index -> binary digit mapping of upstream Rust."""
    exponent_bits, mantissa_bits = (8, 23) if bits == 32 else (11, 52)
    bias = (1 << (exponent_bits - 1)) - 1
    assert raw >> (bits - 1) == 0, "precondition: nonnegative probability"
    raw_exponent = (raw >> mantissa_bits) & ((1 << exponent_bits) - 1)
    assert raw_exponent <= bias, "precondition: probability no greater than one"
    assert raw_exponent != bias or (raw & ((1 << mantissa_bits) - 1)) == 0
    if raw_exponent == bias:
        return Fraction(1)  # p == 1.0 early return

    max_coin_flips = bias + mantissa_bits
    buffer_len = (max_coin_flips + 7) // 8
    limit = buffer_len * 8
    leading_zeros = bias - 1 - raw_exponent

    # The geometric first-head index i has probability 2**(-i-1).
    # Sum the dyadic digits using integers, with no floating-point rounding.
    numerator = 0
    for i in range(limit):
        if i < leading_zeros:
            bit = False
        elif i == leading_zeros:
            bit = raw_exponent != 0
        elif i > leading_zeros + mantissa_bits:
            bit = False
        else:
            bit = bool(raw & (1 << (leading_zeros + mantissa_bits - i)))
        if bit:
            numerator |= 1 << (limit - i - 1)
    return Fraction(numerator, 1 << limit)


class BernoulliFloatSubnormalModelTests(unittest.TestCase):
    def test_exact_subnormal_law(self):
        rng = random.Random(20261122)
        for bits in (32, 64):
            mantissa_bits = 23 if bits == 32 else 52
            samples = [1, 2, 3, 5, 1 << (mantissa_bits - 1),
                       (1 << mantissa_bits) - 1]
            samples += [rng.randrange(1, 1 << mantissa_bits)
                        for _ in range(256)]
            for raw in samples:
                intended = Fraction.from_float(binary_float(raw, bits))
                self.assertEqual(implied_success_probability(raw, bits),
                                 intended / 2, (bits, raw))

    def test_exact_normal_law(self):
        rng = random.Random(20261122)
        for bits in (32, 64):
            e_bits, m_bits = (8, 23) if bits == 32 else (11, 52)
            bias = (1 << (e_bits - 1)) - 1
            exponents = [1, 2, bias // 2, bias - 1, bias]
            cases = [1 << m_bits, bias << m_bits, 0]
            # Random nonnegative finite normals p <= 1; 1 uses early return.
            for _ in range(256):
                exponent = rng.choice(exponents)
                mantissa = 0 if exponent == bias else rng.randrange(1 << m_bits)
                cases.append((exponent << m_bits) | mantissa)
            for raw in cases:
                intended = Fraction.from_float(binary_float(raw, bits))
                self.assertEqual(implied_success_probability(raw, bits),
                                 intended, (bits, raw))

    def test_min_normal_transition(self):
        for bits in (32, 64):
            m_bits = 23 if bits == 32 else 52
            max_subnormal = (1 << m_bits) - 1
            min_normal = 1 << m_bits
            sub = Fraction.from_float(binary_float(max_subnormal, bits))
            normal = Fraction.from_float(binary_float(min_normal, bits))
            self.assertEqual(implied_success_probability(max_subnormal, bits),
                             sub / 2)
            self.assertEqual(implied_success_probability(min_normal, bits),
                             normal)


if __name__ == "__main__":
    unittest.main()
