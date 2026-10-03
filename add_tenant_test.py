import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE_URL = "http://127.0.0.1:5000"

print("=== Apartment Rent Manager - Add Tenant Test ===")
print()

house_number = input("House number (example: House 1): ").strip()
tenant_name = input("Tenant name: ").strip()
phone = input("Phone: ").strip()
monthly_rent = input("Monthly rent (example: 3000): ").strip()
advance_amount = input("Advance amount (example: 10000): ").strip()
join_date = input("Join date (YYYY-MM-DD): ").strip()

payload = {
    "house_number": house_number,
    "tenant_name": tenant_name,
    "phone": phone,
    "monthly_rent": monthly_rent,
    "advance_amount": advance_amount,
    "join_date": join_date
}

url = BASE_URL + "/api/tenants"

try:
    data = json.dumps(payload).encode("utf-8")

    request = Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urlopen(request, timeout=15) as response:
        result = json.loads(response.read().decode("utf-8"))
        print()
        print("STATUS:", response.status)
        print(json.dumps(result, indent=2))

except HTTPError as e:
    body = e.read().decode("utf-8", errors="replace")
    print()
    print("HTTP ERROR:", e.code)
    try:
        print(json.dumps(json.loads(body), indent=2))
    except Exception:
        print(body)

except URLError as e:
    print()
    print("Could not connect to Flask.")
    print("Make sure this is running first:")
    print("    python app.py")
    print("Error:", e)

except Exception as e:
    print()
    print("ERROR:", e)
