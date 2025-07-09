from jwcrypto import jwk
import json

# === 1. RSA鍵生成 ===
key = jwk.JWK.generate(kty='RSA', alg='RS256', use='sig', size=2048)

# === 2. JWK JSON 形式をエクスポート ===
private_key_jwk = key.export_private()
public_key_jwk = key.export_public()

print("=== private key (JWK) ===")
print(json.dumps(json.loads(private_key_jwk), indent=2))

print("\n=== public key (JWK) ===")
print(json.dumps(json.loads(public_key_jwk), indent=2))

# === 3. PEM形式でエクスポート ===
pem_private = key.export_to_pem(private_key=True, password=None).decode()
pem_public = key.export_to_pem().decode()

print("\n=== private.pem ===")
print(pem_private)

print("\n=== public.pem ===")
print(pem_public)

# === 4. ファイル保存 ===
with open("private.pem", "w") as f:
    f.write(pem_private)

with open("public.pem", "w") as f:
    f.write(pem_public)

print("\n✔️ private.pem / public.pem saved.")
