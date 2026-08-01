# Diffie–Hellman Key Exchange

This is a cryptographic method that lets two parties agree on a shared secret that a passive eavesdropper can't learn (authentication must be added separately) thanks to modular math.

## My Understanding

### Step 1: Both parties agree on public parameters.

Party A + Party B -> Agree on modulus (m) and base (g).

### Step 2: Both parties decide on a secret number.

Party A -> decides on a secret number (a)
Party B -> decides on a secret number (b)

### Step 3: Both parties generate their public keys using the agreed upon parameter.

Party A -> generates `g ^ a mod m` (A)
Party B -> generates `g ^ b mod m` (B)

### Step 4: Both parties share these with one another.

Party A -> Shares A with Party B
Party B -> Shares B with party A

### Step 5: They can now generate their shared secret.

Party A -> `B ^ a mod m` (i.e. `(g ^ b) mod m ^ a mod m` = `g ^ (b * a) mod m`)
Party B -> `A ^ b mod m` (i.e. `(g ^ a) mod m ^ b mod m` = `g ^ (a * b) mod m`)

## Why they reach the same shared secret

`g ^ (b * a) mod m` = `g ^ (a * b) mod m` - multiplication doesn't care about order.

## Why an outsider is left in the dust

They see g, m, A, and B, - everything except a and b. They would run into a discrete logarithm problem trying to compute a from g, m, and A.

## Example

`g = 5`, `mod 23`

Me: `private = 4`, I send them `public: 5 ^ 4 mod 23 = 4`
Friend: `private = 3`, send `public: 5 ^ 3 mod 23 = 10`

I compute `shared: 10 ^ 4 mod 23 = 18`
They compute `shared: 4 ^ 3 mod 23 = 18`

# Why authentication is still required

DH is still vulnerable to a man-in-the-middle attack. Someone could insert themselves in the middle of communication and do separate DH with each party and relay messages, and neither side would be any the wiser. In other words DH gives you a shared secret but no proof of who you shared it with.

In this project I assume that the two parties have agreed upon a shared password that's mixed in with the derived key so that the sender can be authenticated by both parties using this mutually known password - the man in the middle ends up with a different key and can be booted after the key verification step fails (assuming the password remains secret).

# Something worth noting

This project uses X25519 which is the elliptic-curve version of the modular understanding. Same thing conceptually but harder to break and with shorter keys.