import ctypes
import sys
import os

class Share(ctypes.Structure):
    _fields_ = [("x", ctypes.c_int),
                ("y", ctypes.c_int)]

# Resolve library path relative to current module
_base_dir = os.path.dirname(os.path.abspath(__file__))

if sys.platform.startswith("win"):
    lib_path = os.path.join(_base_dir, "Engine.dll")
elif sys.platform.startswith("linux"):
    lib_path = os.path.join(_base_dir, "Engine.so")
else:
    raise OSError("Unsupported operating system")

lib = ctypes.CDLL(lib_path)

# Function declarations

lib.lagrange_interpolation.argtypes = [ctypes.c_int, ctypes.POINTER(Share), ctypes.c_int]
lib.lagrange_interpolation.restype = ctypes.c_int

def lagrange_interpolation(x, shares, n):
    shares_array = (Share * n)(*shares)
    res = lib.lagrange_interpolation(x, shares_array, n)
    if res < 0:
        raise ValueError("Lagrange interpolation failed (e.g. duplicate coordinates or zero division)")
    return res

lib.evaluate_share.argtypes = [ctypes.POINTER(Share), ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.c_int]
lib.evaluate_share.restype = None

def evaluate_share(share, x, coeffs, degree):
    lib.evaluate_share(share, x, coeffs, degree)

lib.generate_random_coeffs.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_int]
lib.generate_random_coeffs.restype = ctypes.c_int

def generate_random_coeffs(coeffs, degree):
    status = lib.generate_random_coeffs(coeffs, degree)
    if status != 0:
        raise RuntimeError("CSPRNG failure in C engine")

lib.evaluate_share_batch.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
lib.evaluate_share_batch.restype = ctypes.c_int

def evaluate_share_batch(xs, secret_bytes, num_bytes, degree):
    num_shares = len(xs)
    if num_shares <= 0 or num_bytes <= 0 or len(secret_bytes) != num_bytes:
        raise ValueError("Invalid share or secret byte count")

    xs_arr = (ctypes.c_int * num_shares)(*xs)
    secret_arr = (ctypes.c_int * num_bytes)(*secret_bytes)
    
    out_ys = (ctypes.c_int * (num_shares * num_bytes))()
    
    status = lib.evaluate_share_batch(xs_arr, num_shares, secret_arr, num_bytes, degree, out_ys)
    if status == -1:
        raise MemoryError("Memory allocation failed in C engine")
    elif status == -2:
        raise ValueError("Invalid arguments passed to C engine")
    elif status == -3:
        raise RuntimeError("CSPRNG failure in C engine")
    elif status != 0:
        raise RuntimeError(f"Error in evaluate_share_batch: status={status}")

    flat_list = list(out_ys)
    return [flat_list[i * num_bytes : (i + 1) * num_bytes] for i in range(num_shares)]

lib.lagrange_interpolation_batch.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
lib.lagrange_interpolation_batch.restype = ctypes.c_int

def lagrange_interpolation_batch(xs, ys_matrix, num_shares, num_bytes):
    if num_shares <= 0 or num_bytes <= 0 or len(xs) != num_shares or len(ys_matrix) != num_shares:
        raise ValueError("Invalid share count or matrix dimensions")

    xs_arr = (ctypes.c_int * num_shares)(*xs)

    flat_ys = [y for row in ys_matrix for y in row]
    if len(flat_ys) != num_shares * num_bytes:
        raise ValueError("Mismatch between matrix shape and num_bytes")

    ys_arr = (ctypes.c_int * len(flat_ys))(*flat_ys)
    
    out_secret = (ctypes.c_int * num_bytes)()
    status = lib.lagrange_interpolation_batch(xs_arr, ys_arr, num_shares, num_bytes, out_secret)
    if status == -1:
        raise MemoryError("Memory allocation failed in C engine")
    elif status == -2:
        raise ValueError("Invalid arguments passed to C engine")
    elif status == -4:
        raise ValueError("Lagrange interpolation failed (e.g. duplicate coordinates or zero division)")
    elif status != 0:
        raise RuntimeError(f"Error in lagrange_interpolation_batch: status={status}")

    return list(out_secret)