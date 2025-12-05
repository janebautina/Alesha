#!/usr/bin/env python3
"""
test_payment_settings.py — small helper to verify payment settings in Supabase.

- Reads rows from public.streamer_settings
- Prints card_number_full (masked), buymeacoffee_link, donation_alerts_link
- Helps you confirm that Alesha will show the correct donation info on stream
"""

from typing import Optional
from db import get_supabase


def mask_card(card: Optional[str]) -> str:
    """
    Mask a card number so logs do not leak the full value.
    Example: '1234567812345678' -> '**** **** **** 5678'
    """
    if not card:
        return "(empty)"

    clean = card.replace(" ", "")
    if len(clean) < 4:
        return "****"

    last4 = clean[-4:]
    return f"**** **** **** {last4}"


def show_payment_settings(limit: int = 5) -> None:
    client = get_supabase()
    if client is None:
        print("🚫 Supabase client is not initialized. Check config.json (SUPABASE_URL / SUPABASE_KEY).")
        return

    try:
        resp = (
            client
            .table("streamer_settings")
            .select("id, streamer_id, card_number_full, buymeacoffee_link, donation_alerts_link")
            .limit(limit)
            .execute()
        )
        rows = resp.data or []
        print(f"\n🗂 Found {len(rows)} row(s) in 'streamer_settings' (showing up to {limit}):\n")

        for row in rows:
            sid = row.get("id")
            streamer_id = row.get("streamer_id")
            card_raw = row.get("card_number_full")
            bmc = row.get("buymeacoffee_link")
            alerts = row.get("donation_alerts_link")

            print(f"- id={sid}")
            print(f"  streamer_id      = {streamer_id}")
            print(f"  card_number_full = {mask_card(card_raw)}")
            print(f"  buymeacoffee     = {bmc or '(empty)'}")
            print(f"  donation_alerts  = {alerts or '(empty)'}")
            print()

    except Exception as e:
        print(f"⚠ Error querying streamer_settings: {e}")


if __name__ == "__main__":
    show_payment_settings()
