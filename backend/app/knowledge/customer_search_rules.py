"""Bottler-aware valid (Account Group, Distribution Channel) combinations.

Encodes the Apex rules from `conaDataChangeController`:
- getExistingCustomers
- getPayerAccountsBySalesOffice
- getFsvRecipientAccounts

Bottler codes:
- 4600 = Reyes
- 4900 = Abarta
- 5000 = Northeast
"""

from __future__ import annotations

from dataclasses import dataclass


BOTTLER_5000 = "5000"  # Northeast
BOTTLER_4900 = "4900"  # Abarta
BOTTLER_4600 = "4600"  # Reyes

KNOWN_BOTTLERS = frozenset({BOTTLER_5000, BOTTLER_4900, BOTTLER_4600})

PAYER_OFFICE = "Payer"
FSV_RECIPIENT_OFFICE = "FSV Recipient"


@dataclass(frozen=True)
class GroupChannelCombo:
    account_group: str
    distribution_channel: str | None = None  # None means "any/unspecified"

    def to_dict(self) -> dict[str, str | None]:
        return {
            "account_group": self.account_group,
            "distribution_channel": self.distribution_channel,
        }


def _normalize_office(sales_office: str | None) -> str | None:
    if not sales_office:
        return None
    return sales_office.strip()


def valid_combinations(
    bottler: str | None,
    sales_office: str | None = None,
) -> list[dict[str, str | None]]:
    """Return list of valid {account_group, distribution_channel} for bottler/office.

    Mirrors the Apex SOQL filters in conaDataChangeController.
    Returns empty list if bottler unknown.
    """
    if not bottler or bottler not in KNOWN_BOTTLERS:
        return []

    office = _normalize_office(sales_office)
    combos: list[GroupChannelCombo] = []

    if bottler == BOTTLER_5000:
        # Northeast: Z001 only (existing customers) + Z003 for payer office.
        if office and office.lower() == PAYER_OFFICE.lower():
            combos.append(GroupChannelCombo(account_group="Z003"))
        else:
            combos.append(GroupChannelCombo(account_group="Z001"))
            # Empty office runs both queries; still allow Z003 for completeness.
            if not office:
                combos.append(GroupChannelCombo(account_group="Z003"))

    elif bottler == BOTTLER_4900:
        # Abarta
        if office and office.lower() == FSV_RECIPIENT_OFFICE.lower():
            combos.append(GroupChannelCombo("Z003", "Z3"))
        elif office and office.lower() == PAYER_OFFICE.lower():
            combos.append(GroupChannelCombo("Z003", "Z1"))
        elif office:
            # Strict with sales office set
            combos.append(GroupChannelCombo("Z001", "Z1"))
            combos.append(GroupChannelCombo("ZFSV", "Z3"))
        else:
            # No office
            combos.append(GroupChannelCombo("Z001", "Z1"))
            combos.append(GroupChannelCombo("ZFSV", "Z3"))
            combos.append(GroupChannelCombo("Z003", "Z1"))
            combos.append(GroupChannelCombo("Z003", "Z3"))

    elif bottler == BOTTLER_4600:
        # Reyes
        if office and office.lower() == PAYER_OFFICE.lower():
            combos.append(GroupChannelCombo("Z003", "Z1"))
        else:
            combos.append(GroupChannelCombo("Z001"))
            combos.append(GroupChannelCombo("ZFSV"))
            combos.append(GroupChannelCombo("Z003"))

    return [c.to_dict() for c in combos]


def is_valid_combo(
    bottler: str | None,
    sales_office: str | None,
    account_group: str | None,
    distribution_channel: str | None,
) -> bool:
    if not account_group:
        return False
    for combo in valid_combinations(bottler, sales_office):
        if combo["account_group"] != account_group:
            continue
        allowed_channel = combo["distribution_channel"]
        if allowed_channel is None:
            return True
        if allowed_channel == distribution_channel:
            return True
    return False


def known_account_groups(bottler: str | None) -> list[str]:
    seen: list[str] = []
    for office in (None, PAYER_OFFICE, FSV_RECIPIENT_OFFICE):
        for combo in valid_combinations(bottler, office):
            ag = combo["account_group"]
            if ag and ag not in seen:
                seen.append(ag)
    return seen


def known_distribution_channels(bottler: str | None, account_group: str | None) -> list[str]:
    seen: list[str] = []
    for office in (None, PAYER_OFFICE, FSV_RECIPIENT_OFFICE):
        for combo in valid_combinations(bottler, office):
            if combo["account_group"] != account_group:
                continue
            ch = combo["distribution_channel"]
            if ch and ch not in seen:
                seen.append(ch)
    return seen


def default_soql_for_bottler(bottler: str | None) -> str:
    """Return a starter SOQL query for the bottler that respects Apex filters."""
    if bottler == BOTTLER_5000:
        return (
            "SELECT Id, AccountNumber, Name, cfs_ob__u_CustomerNumber__c, "
            "cfs_ob__u_ActiveCustomer__c, cfs_ob__u_SalesOffice__c, "
            "cfs_ob__u_CustomerAccountGroup__c, cfs_ob__Bottler__c "
            "FROM Account "
            "WHERE cfs_ob__u_CustomerAccountGroup__c = 'Z001' "
            "AND cfs_ob__Bottler__c = '5000' "
            "AND cfs_ob__u_ActiveCustomer__c = true "
            "LIMIT 50"
        )

    fields = (
        "SELECT AccountNumber, Name, cfs_ob__u_SalesOffice__c, "
        "cfs_ob__u_CustomerAccountGroup__c, cfs_ob__u_DistributionChannel__c, "
        "cfs_ob__u_ActiveCustomer__c, cfs_ob__Bottler__c"
    )
    base_filters = [
        "AccountNumber != NULL",
        "cfs_ob__u_ActiveCustomer__c = true",
        "(MarkforDeletion__c = false OR MarkforDeletion__c = null)",
    ]
    if bottler == BOTTLER_4900:
        base_filters.append(
            "((cfs_ob__u_CustomerAccountGroup__c = 'Z001' "
            "AND cfs_ob__u_DistributionChannel__c = 'Z1') OR "
            "(cfs_ob__u_CustomerAccountGroup__c = 'ZFSV' "
            "AND cfs_ob__u_DistributionChannel__c = 'Z3'))"
        )
    elif bottler == BOTTLER_4600:
        base_filters.append(
            "cfs_ob__u_CustomerAccountGroup__c IN ('Z001', 'ZFSV', 'Z003')"
        )
    where = " AND ".join(base_filters)
    return f"{fields} FROM Account WHERE {where} LIMIT 5"
