import ctypes
import sys

class Share(ctypes.Structure):
    _fields_ = [("x", ctypes.c_int),
                ("y", ctypes.c_int)]
    
# Detect operating system and load the c lib
if sys.platform.startswith("win"):
    lib = ctypes.CDLL("Engine.dll")
elif sys.platform.startswith("linux"):
    lib = ctypes.CDLL("./Engine.so")
else:
    raise OSError("Unsupported operating system")

# Define funcs

lib.lagrange_interpolation.argtypes = [ctypes.c_int, ctypes.POINTER(Share), ctypes.c_int, ctypes.c_int]
lib.lagrange_interpolation.restype = ctypes.c_int

def lagrange_interpolation(x, shares, n, p):
    shares_array = (Share * n)(*shares)
    return lib.lagrange_interpolation(x, shares_array, n, p)

lib.evaluate_share.argtypes = [ctypes.POINTER(Share), ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.c_int, ctypes.c_int]
lib.evaluate_share.restype = None

def evaluate_share(share, x, coeffs, degree, p):
    lib.evaluate_share(share, x, coeffs, degree, p)

lib.generate_random_coeffs.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_int, ctypes.c_int]
lib.generate_random_coeffs.restype = None

def generate_random_coeffs(coeffs, degree, p):
    lib.generate_random_coeffs(coeffs, degree, p)
