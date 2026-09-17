import unittest
import os
import py_engine_interpretor as pe

class TestEngineMath(unittest.TestCase):
    def test_single_byte_interpolation(self):
        # f(x) = 42 + 10*x (mod 257)
        # f(1) = 52
        # f(2) = 62
        # f(3) = 72
        shares = [pe.Share(1, 52), pe.Share(2, 62)]
        # Evaluate secret at x = 0
        recovered_secret = pe.lagrange_interpolation(0, shares, 2)
        self.assertEqual(recovered_secret, 42)

        # Evaluate at an arbitrary coordinate x = 3
        recovered_point = pe.lagrange_interpolation(3, shares, 2)
        self.assertEqual(recovered_point, 72)

    def test_duplicate_coordinates_fails_cleanly(self):
        shares = [pe.Share(1, 52), pe.Share(1, 52)]
        with self.assertRaises(ValueError):
            pe.lagrange_interpolation(0, shares, 2)

    def test_aes_key_batch_reconstruction_all_subsets(self):
        secret_key = list(os.urandom(32))
        xs = [1, 2, 3]
        shares = pe.evaluate_share_batch(xs, secret_key, len(secret_key), degree=1)
        self.assertEqual(len(shares), 3)

        # Subset {1, 2}
        rec_12 = pe.lagrange_interpolation_batch([1, 2], [shares[0], shares[1]], 2, 32)
        self.assertEqual(rec_12, secret_key)

        # Subset {2, 3}
        rec_23 = pe.lagrange_interpolation_batch([2, 3], [shares[1], shares[2]], 2, 32)
        self.assertEqual(rec_23, secret_key)

        # Subset {1, 3}
        rec_13 = pe.lagrange_interpolation_batch([1, 3], [shares[0], shares[2]], 2, 32)
        self.assertEqual(rec_13, secret_key)

        # Full set {1, 2, 3}
        rec_all = pe.lagrange_interpolation_batch([1, 2, 3], shares, 3, 32)
        self.assertEqual(rec_all, secret_key)

    def test_boundary_byte_values(self):
        # Test extreme byte values: 0, 1, 127, 128, 254, 255
        boundary_secret = [0, 1, 127, 128, 254, 255] * 5 + [0, 255]
        self.assertEqual(len(boundary_secret), 32)
        
        xs = [1, 2, 3]
        shares = pe.evaluate_share_batch(xs, boundary_secret, 32, degree=1)
        rec = pe.lagrange_interpolation_batch([1, 3], [shares[0], shares[2]], 2, 32)
        self.assertEqual(rec, boundary_secret)

    def test_duplicate_shares_batch_raises(self):
        secret_key = list(range(32))
        shares = pe.evaluate_share_batch([1, 2], secret_key, 32, degree=1)
        with self.assertRaises(ValueError):
            # Duplicate coordinate x = 1
            pe.lagrange_interpolation_batch([1, 1], [shares[0], shares[0]], 2, 32)

    def test_invalid_arguments_batch(self):
        with self.assertRaises(ValueError):
            pe.evaluate_share_batch([], [1, 2, 3], 0, 1)

if __name__ == "__main__":
    unittest.main()
