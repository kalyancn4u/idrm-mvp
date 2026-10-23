"""Generate the RS256 JWT keypair into ./keys/."""

from __future__ import annotations

from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

KEYS_DIR = Path("keys")


def main() -> None:
    KEYS_DIR.mkdir(exist_ok=True)
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    (KEYS_DIR / "jwt_private.pem").write_bytes(
        private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    (KEYS_DIR / "jwt_public.pem").write_bytes(
        private.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    print("✔ keys/jwt_private.pem")
    print("✔ keys/jwt_public.pem")


if __name__ == "__main__":
    main()

