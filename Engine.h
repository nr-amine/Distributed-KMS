// This file is the main engine for the key management system.
// It uses shamir's secret sharing scheme to split a secret into multiple shares and reconstruct it when needed.
// The engine provides functions to create shares, reconstruct the secret, and manage the shares.

#ifndef ENGINE_H
#define ENGINE_H

#include <windows.h>
#include <stdio.h>
#include <bcrypt.h>
#include <stdlib.h>

struct Share {
    int x;
    int y;
};

int mod(int a, int b);
int mod_inverse(int a, int p);
int mod_pow(int base, int exp, int mod);
int mod_div(int a, int b, int p);
int mod_mult(int a, int b, int p);
int mod_add(int a, int b, int p);
int mod_sub(int a, int b, int p);
int generate_random_signed_int();
void generate_random_coeffs(int *coeffs, int degree, int p);
void evaluate_share(struct Share *share, int x, int *coeffs, int degree, int p);
int lagrange_interpolation(int x, struct Share *shares, int n, int p);


#endif // ENGINE_H