"""Run an EcoCash Instant Payment sandbox charge or auth check.

Credentials are read from web/ecocash-scandbox.md (gitignored) or
ECOCASH_USERNAME / ECOCASH_PASSWORD. The test MSISDN must be whitelisted
and OTP-verified in the EcoCash developer portal.
"""

import argparse
import base64
import json
import os
import time
import uuid
from pathlib import Path

import httpx

BASE_URL = os.getenv(
    "ECOCASH_BASE_URL", "https://developers.ecocash.co.zw/sandbox/payment/v1"
)
CREDENTIALS_FILE = Path("web/ecocash-scandbox.md")


def credentials() -> tuple[str, str]:
    username = os.getenv("ECOCASH_USERNAME")
    password = os.getenv("ECOCASH_PASSWORD")
    if username and password:
        return username, password

    if not CREDENTIALS_FILE.exists():
        raise SystemExit("Set ECOCASH_USERNAME/ECOCASH_PASSWORD or create the sandbox file")
    lines = [line.strip() for line in CREDENTIALS_FILE.read_text(encoding="utf-8").splitlines()]
    username = next((line for line in lines if line.startswith("sbx_")), None)
    password = next(
        (
            line
            for line in lines
            if line
            and not line.startswith("sbx_")
            and line not in {"Username", "Password"}
        ),
        None,
    )
    if not username or not password:
        raise SystemExit("Could not read EcoCash sandbox credentials")
    return username, password


def auth_header() -> str:
    username, password = credentials()
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


def auth_only(msisdn: str) -> None:
    response = httpx.get(
        f"{BASE_URL}/{msisdn}/transactions/amount/auth-{uuid.uuid4().hex[:8]}",
        headers={"Authorization": auth_header()},
        timeout=30,
    )
    print("status", response.status_code)
    print(response.text[:800])


def charge(msisdn: str, amount: str) -> None:
    correlator = f"MK-{int(time.time())}-{uuid.uuid4().hex[:6]}"
    payload = {
        "clientCorrelator": correlator,
        "notifyUrl": "",
        "referenceCode": f"MUKANA-{correlator}",
        "tranType": "MER",
        "endUserId": msisdn,
        "remarks": "Mukana EcoCash sandbox test",
        "transactionOperationStatus": "Charged",
        "paymentAmount": {
            "charginginformation": {
                "amount": amount,
                "currency": "USD",
                "description": "Mukana sandbox test",
            },
            "chargeMetaData": {"channel": "WEB"},
        },
        "merchantCode": os.getenv("ECOCASH_MERCHANT_CODE", "287164"),
        "merchantPin": os.getenv("ECOCASH_MERCHANT_PIN", "1234"),
        "merchantNumber": os.getenv("ECOCASH_MERCHANT_NUMBER", "778503033"),
        "countryCode": "ZW",
        "terminalID": os.getenv("ECOCASH_TERMINAL_ID", "TERM001"),
        "location": "Harare",
        "superMerchantName": "EcoCash Sandbox",
        "merchantName": "Test Merchant",
    }
    response = httpx.post(
        f"{BASE_URL}/transactions/amount/",
        headers={"Authorization": auth_header(), "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    print("charge", response.status_code)
    try:
        body = response.json()
    except ValueError:
        print(response.text[:800])
        return
    print(json.dumps(body, indent=2)[:1200])
    if response.status_code >= 400:
        return

    for attempt in range(20):
        time.sleep(3)
        lookup = httpx.get(
            f"{BASE_URL}/{msisdn}/transactions/amount/{correlator}",
            headers={"Authorization": auth_header()},
            timeout=30,
        )
        try:
            state = lookup.json()
        except ValueError:
            print("lookup", lookup.status_code, lookup.text[:500])
            continue
        print(
            f"lookup {attempt + 1}: {state.get('status')} {state.get('statusMessage') or ''}"
        )
        if state.get("status") not in {"PENDING", None}:
            print(json.dumps(state, indent=2)[:1200])
            return


def main() -> None:
    parser = argparse.ArgumentParser(description="EcoCash sandbox smoke test")
    parser.add_argument("--msisdn", help="Whitelisted test MSISDN, e.g. 263771234567")
    parser.add_argument("--amount", default="1.00")
    parser.add_argument("--auth-only", action="store_true")
    args = parser.parse_args()

    if not args.msisdn:
        parser.error("--msisdn is required")
    if args.auth_only:
        auth_only(args.msisdn)
    else:
        charge(args.msisdn, args.amount)


if __name__ == "__main__":
    main()
