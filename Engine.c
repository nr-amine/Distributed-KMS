// Finite field arithmetic and Shamir's Secret Sharing core.
// Splits a secret byte-by-byte over the prime field GF(257).
// Since each byte in an AES key is in [0, 255] < 257, operations fit in standard integer types.

#include "Engine.h"

#ifdef _WIN32
    #define SHOULD_EXPORT __declspec(dllexport)
#else
    #define SHOULD_EXPORT
#endif

#define P 257 // Prime modulus for GF(257)

// ------------ Finite field arithmetic ------------

int mod(int a, int b) {
    int r = a % b;
    return r < 0 ? r + b : r;
}

// Modular inverse via the Extended Euclidean Algorithm:
// Computes u such that a * u = 1 (mod p). Returns -1 if no inverse exists (e.g., gcd(a, p) != 1).
int mod_inverse(int a, int p) {
    a = mod(a, p);
    if (a == 0 || p <= 1) {
        return -1;
    }

    int m0 = p, t, q;
    int x0 = 0, x1 = 1;

    while (a > 1) {
        if (p == 0) {
            return -1;
        }
        q = a / p;
        t = p;
        p = a % p;
        a = t;
        t = x0;
        x0 = x1 - q * x0;
        x1 = t;
    }

    if (x1 < 0) {
        x1 += m0;
    }

    return x1;
}

int mod_pow(int base, int exp, int modus) {
    int result = 1;
    base = mod(base, modus);
    while (exp > 0) {
        if (exp % 2 == 1) {
            result = mod(result * base, modus);
        }
        exp = exp >> 1;
        base = mod(base * base, modus);
    }
    return result;
}

int mod_div(int a, int b, int p) {
    int inv = mod_inverse(b, p);
    if (inv < 0) {
        return -1;
    }
    return mod(a * inv, p);
}

int mod_mult(int a, int b, int p) {
    return mod(a * b, p);
}

int mod_add(int a, int b, int p) {
    return mod(a + b, p);
}

int mod_sub(int a, int b, int p) {
    return mod(a - b, p);
}

// ------------ OS Cryptographically Secure RNG ------------

#ifdef _WIN32
#include <windows.h>
#include <bcrypt.h>

int generate_random_uint32(uint32_t *out) {
    if (BCryptGenRandom(NULL, (PUCHAR)out, sizeof(*out), BCRYPT_USE_SYSTEM_PREFERRED_RNG) != 0) {
        return -1;
    }
    return 0;
}

#elif defined(__linux__) || defined(__APPLE__)
#include <unistd.h>
#include <sys/random.h>
#include <errno.h>

int generate_random_uint32(uint32_t *out) {
    ssize_t ret;
    do {
        ret = getrandom(out, sizeof(*out), 0);
    } while (ret == -1 && errno == EINTR);

    if (ret != (ssize_t)sizeof(*out)) {
        return -1;
    }
    return 0;
}
#else
#error "Unsupported platform"
#endif

// Rejection sampling modulo 257:
// 2^32 = 16711935 * 257 + 1. We reject UINT32_MAX (4294967295) to guarantee zero modulo bias.
int get_random_coeff(int *out) {
    uint32_t val;
    do {
        if (generate_random_uint32(&val) != 0) {
            return -1;
        }
    } while (val == UINT32_MAX);

    *out = (int)(val % P);
    return 0;
}

SHOULD_EXPORT int generate_random_coeffs(int *coeffs, int degree) {
    for (int i = 1; i <= degree; i++) {
        if (get_random_coeff(&coeffs[i]) != 0) {
            return -1;
        }
    }
    return 0;
}

//------------- Shamir's Secret Sharing Scheme functions ------------

// Evaluates polynomial P(x) = coeffs[0] + coeffs[1]*x + ... + coeffs[degree]*x^degree modulo P via Horner's method.
SHOULD_EXPORT void evaluate_share(struct Share *share, int x, int *coeffs, int degree) {
    int res = 0;
    for (int i = degree; i >= 0; i--) {
        res = mod_add(mod_mult(res, x, P), coeffs[i], P);
    }
    share->x = x;
    share->y = res;
}

// Lagrange interpolation: reconstructs P(x) given n shares (x_i, y_i) in GF(257).
// Returns the evaluated integer in [0, P-1], or -1 on duplicate coordinates / division by zero.
SHOULD_EXPORT int lagrange_interpolation(int x, struct Share *shares, int n) {
    int S = 0; 
    for (int i = 0; i < n; i++) {
        int num = 1;
        int den = 1;
        for (int j = 0; j < n; j++) {
            if (i != j) {
                if (shares[i].x == shares[j].x) {
                    return -1; // Duplicate share coordinates
                }
                num = mod_mult(num, mod_sub(x, shares[j].x, P), P);
                den = mod_mult(den, mod_sub(shares[i].x, shares[j].x, P), P);
            }
        }
        int div = mod_div(num, den, P);
        if (div < 0) {
            return -1;
        }
        S = mod_add(S, mod_mult(shares[i].y, div, P), P);
    }
    return S;   
}

// Evaluates shares for an array of secret bytes.
// Returns 0 on success, or a negative status code on error.
SHOULD_EXPORT int evaluate_share_batch(int *xs, int num_shares, int *secret_bytes, int num_bytes, int degree, int *out_ys_matrix) {
    if (degree < 0 || num_shares <= 0 || num_bytes <= 0) {
        return -2; // Invalid arguments
    }

    int *coeffs = (int *)malloc((degree + 1) * sizeof(int));
    if (coeffs == NULL) {
        return -1; // Memory allocation failed
    }
    
    for (int b = 0; b < num_bytes; b++) {
        if (generate_random_coeffs(coeffs, degree) != 0) {
            free(coeffs);
            return -3; // CSPRNG failure
        }
        coeffs[0] = secret_bytes[b];
        
        for (int i = 0; i < num_shares; i++) {
            int x = xs[i];
            int res = 0;
            
            for (int j = degree; j >= 0; j--) {
                res = mod_add(mod_mult(res, x, P), coeffs[j], P);
            }
            
            out_ys_matrix[i * num_bytes + b] = res;
        }
    }
    
    free(coeffs);
    return 0;
}

// Reconstructs secret bytes from share coordinate matrix at x = 0.
// Returns 0 on success, or a negative status code on error.
SHOULD_EXPORT int lagrange_interpolation_batch(int *xs, int *ys_matrix, int num_shares, int num_bytes, int *out_secret) {
    if (num_shares <= 0 || num_bytes <= 0) {
        return -2; // Invalid arguments
    }

    struct Share *shares = (struct Share *)malloc(num_shares * sizeof(struct Share));
    if (shares == NULL) {
        return -1; // Memory allocation failed
    }

    for (int b = 0; b < num_bytes; b++) {
        for (int i = 0; i < num_shares; i++) {
            shares[i].x = xs[i];
            shares[i].y = ys_matrix[i * num_bytes + b]; 
        }
        int recovered = lagrange_interpolation(0, shares, num_shares);
        if (recovered < 0) {
            free(shares);
            return -4; // Math/interpolation error
        }
        out_secret[b] = recovered;
    }
    
    free(shares);
    return 0;
}
