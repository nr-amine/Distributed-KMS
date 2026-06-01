// This file is the main engine for the key management system.
// It uses shamir's secret sharing scheme to split a secret into multiple shares and reconstruct it when needed.
// The engine provides functions to create shares, reconstruct the secret, and manage the shares.

#include "Engine.h"
#ifdef _WIN32
    #define SHOULD_EXPORT __declspec(dllexport)
#else
    #define SHOULD_EXPORT
#endif
// ------------ Functions for finite field arithmetic ------------


int mod(int a, int b) {
    int r = a % b;
    return r < 0 ? r + b : r;
}

int mod_inverse(int a, int p) {
    int m0 = p, t, q;
    int x0 = 0, x1 = 1;

    if (p == 1)
        return 0;

    while (a > 1) {
        q = a / p;
        t = p;
        p = a % p, a = t;
        t = x0;
        x0 = x1 - q * x0;
        x1 = t;
    }

    if (x1 < 0)
        x1 += m0;

    return x1;
}

int mod_pow(int base, int exp, int modus) {
    int result = 1;
    base = mod(base, modus);
    while (exp > 0) {
        if (exp % 2 == 1)
            result = mod(result * base, modus);
        exp = exp >> 1;
        base = mod(base * base, modus);
    }
    return result;
}

int mod_div(int a, int b, int p) {
    return mod(a * mod_inverse(b, p), p);
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

// ------------Random number generation using Windows Crypto API ------------

#ifdef _WIN32

SHOULD_EXPORT int generate_random_signed_int() {
    int random_value;
    // Personal reminder:  (PUCHAR) is a typecast to convert the address of random_value to a pointer to an unsigned char,
    // which is the expected input type for the BCryptGenRandom function.
    // NULL is passed as the first argument to indicate that the default cryptographic provider should be used.
    if (BCryptGenRandom(NULL, (PUCHAR)&random_value, sizeof(random_value), BCRYPT_USE_SYSTEM_PREFERRED_RNG) != 0) {
        fprintf(stderr, "Error generating random number\n");
        exit(EXIT_FAILURE);
    }
    return random_value;
}

#elif defined(__linux__) || defined(__APPLE__)
#include <fcntl.h>
#include <sys/random.h>

int generate_random_signed_int() {
    int random_value;
    if (getrandom(&random_value, sizeof(random_value), 0) == -1) {
        fprintf(stderr, "Error generating random number\n");
        exit(EXIT_FAILURE);
    }
    return random_value;
}

#else
#error "Unsupported platform"
#endif

//------------- Shamir's Secret Sharing Scheme functions ------------

SHOULD_EXPORT void generate_random_coeffs(int *coeffs, int degree, int p) {
    for (int i = 0; i < degree; i++) {
        coeffs[i] = mod(generate_random_signed_int(), p);
    }
}

SHOULD_EXPORT void evaluate_share(struct Share *share, int x, int *coeffs, int degre, int p) {
    int res = 0;
    for(int i=degre; i>=0; i--) {
        res = mod_add(mod_mult(res, x, p), coeffs[i], p);
    }
    share->x = x;
    share->y = res;
}

SHOULD_EXPORT int lagrange_interpolation(int x, struct Share *shares, int n, int p) {
    int S = 0; 
    for(int i=0; i<n; i++) {
        int num = 1; int den = 1;
        for(int j=0; j<n; j++) {
            if (i != j) {
                 num = mod_mult(num, mod_sub(0, shares[j].x, p), p);
                 den = mod_mult(den, mod_sub(shares[i].x, shares[j].x, p), p);
            }
        }
        S = mod_add(S, mod_mult(shares[i].y, mod_div(num, den, p), p), p);
    }
    return S;   
}

