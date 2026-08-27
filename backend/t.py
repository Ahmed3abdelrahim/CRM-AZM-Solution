import requests

B = "http://localhost:8000/api/v1"

# Login
login = requests.post(
    f"{B}/auth/login",
    json={
        "email": "ahmed.hassan@azm-crm.example",
        "password": "ChangeMe#2026"
    },
    timeout=30
)

print("login:", login.status_code)

if login.status_code != 200:
    print(login.text)
    raise SystemExit

tok = login.json()["access_token"]
h = {"Authorization": "Bearer " + tok}

# Find KB search endpoint
path = None

for candidate in [
    "/kb/search",
    "/kb-articles/search",
    "/knowledge-base/search"
]:
    r = requests.get(
        f"{B}{candidate}",
        headers=h,
        params={"q": "password"},
        timeout=180
    )

    if r.status_code != 404:
        path = candidate
        print("endpoint:", path)
        break

if path is None:
    print("no search endpoint found")
    raise SystemExit

# Test Arabic and English searches
for q in [
    "كلمة المرور",
    "reset my password"
]:
    r = requests.get(
        f"{B}{path}",
        headers=h,
        params={"q": q},
        timeout=180
    )

    print("\nquery:", repr(q))
    print("status:", r.status_code)

    try:
        d = r.json()
    except Exception:
        print("response:", r.text[:500])
        continue

    items = d if isinstance(d, list) else d.get("items", [])

    print("results:", len(items))

    for it in items[:3]:
        print(
            "   ",
            it.get("title_ar"),
            "|",
            it.get("title_en")
        )
