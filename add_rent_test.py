import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE_URL = "http://127.0.0.1:5000"

print("=== Apartment Rent Manager - Monthly Rent Test ===")
print()

tenant_id = input("Tenant ID (example: 1): ").strip()
rent_month = input("Rent month (1-12, example: 10): ").strip()
rent_year = input("Rent year (example: 2026): ").strip()
rent_amount = input("Rent amount (example: 3000): ").strip()
paid_amount = input("Paid amount (example: 3000): ").strip()
payment_date = input("Payment date (YYYY-MM-DD, example: 2026-10-02): ").strip()

payload = {
    "tenant_id": int(tenant_id),
    "rent_month": int(rent_month),
    "rent_year": int(rent_year),
    "rent_amount": float(rent_amount),
    "paid_amount": float(paid_amount),
    "payment_date": payment_date
}

url = BASE_URL + "/api/rents"

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
    print("Make sure python app.py is running in another terminal.")
    print("Error:", e)

except Exception as e:
    print()
    print("ERROR:", e)
