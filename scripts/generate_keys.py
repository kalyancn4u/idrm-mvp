"""Generate the RS256 JWT keypair into ./keys/."""

from __future__ import annotations

import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

KEYS_DIR = Path("keys")


def main() -> None:
    KEYS_DIR.mkdir(exist_ok=True)
    private_path = KEYS_DIR / "jwt_private.pem"
    # New keys make every token already issued invalid, i.e. everyone is
    # logged out. So an existing pair is kept unless --force is given.
    if private_path.exists() and "--force" not in sys.argv:
        print("✔ keys already exist — kept (use --force to replace; this logs everyone out)")
        return
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

