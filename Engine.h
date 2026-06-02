
#ifndef ENGINE_H
#define ENGINE_H

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
void generate_random_coeffs(int *coeffs, int degree);
void evaluate_share(struct Share *share, int x, int *coeffs, int degree);
int lagrange_interpolation(int x, struct Share *shares, int n);
void lagrange_interpolation_batch(int *xs, int *ys_matrix, int num_shares, int num_bytes, int *out_secret);
void evaluate_share_batch(int x, int *secret_bytes, int num_bytes, int degree, int *out_y);

#endif // ENGINE_H