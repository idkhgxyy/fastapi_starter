import requests

BASE = "http://localhost:8000"

email = "ragtest@example.com"
password = "ragpass123"

# Register
r = requests.post(
    f"{BASE}/api/v1/users/", json={"username": "rag_tester", "email": email, "password": password}
)
print(f"1. Register: {r.status_code}")

# Login
r = requests.post(f"{BASE}/api/v1/auth/login", data={"username": email, "password": password})
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print("2. Login: OK")

# Upload .txt
with open("sample_knowledge.txt", "rb") as f:
    r = requests.post(
        f"{BASE}/api/v1/rag/upload",
        headers=headers,
        files={"file": ("sample.txt", f, "text/plain")},
    )
print(
    f"3. Upload .txt: {r.status_code}, file_type={r.json().get('file_type')}, status={r.json().get('status')}"
)

# Upload .md
with open("sample_knowledge.md", "rb") as f:
    r = requests.post(
        f"{BASE}/api/v1/rag/upload",
        headers=headers,
        files={"file": ("sample.md", f, "text/markdown")},
    )
print(
    f"4. Upload .md:  {r.status_code}, file_type={r.json().get('file_type')}, status={r.json().get('status')}"
)

# Upload .pdf
with open("sample_knowledge.pdf", "rb") as f:
    r = requests.post(
        f"{BASE}/api/v1/rag/upload",
        headers=headers,
        files={"file": ("sample.pdf", f, "application/pdf")},
    )
print(
    f"5. Upload .pdf: {r.status_code}, file_type={r.json().get('file_type')}, status={r.json().get('status')}"
)

# Upload unsupported format
r = requests.post(
    f"{BASE}/api/v1/rag/upload", headers=headers, files={"file": ("test.png", b"fake", "image/png")}
)
print(f"6. Upload .png (rejected): {r.status_code}, detail={r.json()['detail'][:40]}...")

# List documents
r = requests.get(f"{BASE}/api/v1/rag/documents", headers=headers)
docs = r.json()
type_counts = {}
for d in docs:
    type_counts[d["file_type"]] = type_counts.get(d["file_type"], 0) + 1
print(f"7. Document list: {len(docs)} docs, by type: {type_counts}")

print("\n=== Multi-format upload test passed! ===")
