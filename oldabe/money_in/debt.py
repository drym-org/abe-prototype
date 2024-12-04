import csv
import dataclasses
from dataclasses import astuple
from itertools import accumulate
from ..constants import DEBTS_FILE
from typing import Iterable, List, Set
from ..models import Debt, DebtPayment
from ..tally import Tally
from decimal import Decimal
from ..repos import DebtsRepo
from ..distribution import Distribution
from ..models import Payment


def recalculate_debts(new_debts, debt_payments):
    """
    1. Build a hash of all the processed debts, generating an id for each
       (based on email and payment file).
    2. read the existing debts file, row by row.
    3. if the debt in the row is in the "processed" hash, then write the
       processed version instead of the input version and remove it from the
       hash, otherwise write the input version.
    4. write the debts that remain in the processed hash.
    """
    total_debt_payments = Tally(
        (dp.debt.key(), dp.amount) for dp in debt_payments
    )
    return [
        (
            dataclasses.replace(
                debt,
                amount_paid=debt.amount_paid + total_debt_payments[debt.key()],
            )
            if debt.key() in total_debt_payments
            else debt
        )
        for debt in [*DebtsRepo(), *new_debts]
    ]


def write_debts(debts):
    """ Write the debts to disk, replacing the existing file.
    """
    with open(DEBTS_FILE, "w") as f:
        writer = csv.writer(f)
        for debt in debts:
            writer.writerow(astuple(debt))


def pay_outstanding_debts(
    available_amount: Decimal,
    all_debts: Iterable[Debt],
    payable_contributors: Set[str],
) -> List[DebtPayment]:
    """
    Given an available amount return debt payments for as many debts as can
    be covered
    """
    # TODO: are debts being paid in chronological order? (add test)
    payable_debts = [
        d
        for d in all_debts
        if not d.is_fulfilled() and d.email in payable_contributors
    ]

    cummulative_debt = [
        amount
        for amount in accumulate(
            (d.amount_remaining() for d in payable_debts), initial=0
        )
        if amount <= available_amount
    ]

    return [
        DebtPayment(
            debt=d,
            amount=min(d.amount_remaining(), available_amount - already_paid),
        )
        for d, already_paid in zip(payable_debts, cummulative_debt)
    ]


def create_debts(
    available_amount: Decimal,
    distribution: Distribution,
    payable_contributors: Set[str],
    payment: Payment,
):
    return [
        Debt(
            email=email,
            amount=amount,
            amount_paid=Decimal(0),
            payment_file=payment.file,
        )
        for email, amount in distribution.distribute(available_amount).items()
        if email not in payable_contributors
    ]
