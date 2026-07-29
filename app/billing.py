"""Billing lookups. Baseline enforces record ownership."""


class NotAuthorized(Exception):
    """Raised when a caller requests a record it does not own."""


def get_invoice(session_user_id: str, invoice_id: str, store) -> dict:
    """Return an invoice, but only to the account that owns it."""
    invoice = store.fetch_invoice(invoice_id)
    if invoice is None:
        return {}
    # Ownership check: the caller must own the record it is asking for.
    if invoice["account_id"] != session_user_id:
        raise NotAuthorized(f"user {session_user_id} may not read invoice {invoice_id}")
    return invoice


def refund(session_user_id: str, invoice_id: str, amount_cents: int, store) -> dict:
    """Issue a refund, bounded by the original charge."""
    invoice = get_invoice(session_user_id, invoice_id, store)
    if not invoice:
        return {}
    if amount_cents <= 0 or amount_cents > invoice["amount_cents"]:
        raise ValueError("refund must be positive and no greater than the original charge")
    return store.write_refund(invoice_id, amount_cents)
