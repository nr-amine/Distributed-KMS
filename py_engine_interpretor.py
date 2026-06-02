import ctypes
import sys

class Share(ctypes.Structure):
    _fields_ = [("x", ctypes.c_int),
                ("y", ctypes.c_int)]
    
# Detect operating system and load the c lib
if sys.platform.startswith("win"):
    lib = ctypes.CDLL("./Engine.dll")
elif sys.platform.startswith("linux"):
    lib = ctypes.CDLL("./Engine.so")
else:
    raise OSError("Unsupported operating system")

# Define funcs

lib.lagrange_interpolation.argtypes = [ctypes.c_int, ctypes.POINTER(Share), ctypes.c_int]
lib.lagrange_interpolation.restype = ctypes.c_int

def lagrange_interpolation(x, shares, n):
    shares_array = (Share * n)(*shares)
    return lib.lagrange_interpolation(x, shares_array, n)

lib.evaluate_share.argtypes = [ctypes.POINTER(Share), ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.c_int]
lib.evaluate_share.restype = None

def evaluate_share(share, x, coeffs, degree):
    lib.evaluate_share(share, x, coeffs, degree)

lib.generate_random_coeffs.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_int]
lib.generate_random_coeffs.restype = None

def generate_random_coeffs(coeffs, degree):
    lib.generate_random_coeffs(coeffs, degree)

lib.evaluate_share_batch.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
lib.evaluate_share_batch.restype = None

def evaluate_share_batch(x, secret_bytes, num_bytes, degree):
    secret_arr = (ctypes.c_int * num_bytes)(*secret_bytes)
    out_y = (ctypes.c_int * num_bytes)()
    lib.evaluate_share_batch(x, secret_arr, num_bytes, degree, out_y)
    return list(out_y)

lib.lagrange_interpolation_batch.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
lib.lagrange_interpolation_batch.restype = None

def lagrange_interpolation_batch(xs, ys_matrix, num_shares, num_bytes):
    xs_arr = (ctypes.c_int * num_shares)(*xs)

    flat_ys = [y for row in ys_matrix for y in row]
    ys_arr = (ctypes.c_int * len(flat_ys))(*flat_ys)
    
    out_secret = (ctypes.c_int * num_bytes)()
    lib.lagrange_interpolation_batch(xs_arr, ys_arr, num_shares, num_bytes, out_secret)
    return list(out_secret)