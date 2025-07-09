from jwcrypto import jwk

with open("public.pem", "rb") as f:
    key = jwk.JWK.from_pem(f.read())

print(key.export_public())
