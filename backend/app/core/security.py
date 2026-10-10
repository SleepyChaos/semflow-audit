"""Legacy benchmark fixture hashing; the local application has no authentication."""

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

password_hash = PasswordHash(
    (
        Argon2Hasher(),
        BcryptHasher(),
    )
)


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)
