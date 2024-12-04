#!/usr/bin/env python

from decimal import Decimal
from typing import List, Tuple

from ..accounting import (
    assert_attributions_normalized,
)
from ..tally import Tally
from ..constants import ACCOUNTING_ZERO
from ..distribution import Distribution
from ..models import (
    Advance,
    Debt,
    DebtPayment,
    ItemizedPayment,
    Payment,
    Transaction,
)
from ..repos import (
    AdvancesRepo,
    AllPaymentsRepo,
    AttributionsRepo,
    DebtsRepo,
    InstrumentsRepo,
    ItemizedPaymentsRepo,
    TransactionsRepo,
    UnpayableContributorsRepo,
)
from .price import read_price
from .equity import write_attributions
from .valuation import read_valuation, write_valuation
from .debt import pay_outstanding_debts, create_debts, recalculate_debts, write_debts
from .advances import draw_down_advances, advance_payments
from .equity import handle_investment


def distribute_payment(
    payment: Payment, distribution: Distribution
) -> Tuple[List[Debt], List[DebtPayment], List[Transaction], List[Advance]]:
    """
    Generate transactions to contributors from a (new) payment.

    We consult the attribution file and determine how much is owed
    to each contributor based on the current percentages, generating a
    fresh entry in the transactions file for each contributor.
    """

    # 1. check payable outstanding debts
    # 2. pay them off in chronological order (maybe partially)
    # 3. (if leftover) identify unpayable people in the relevant
    #    distribution file
    # 4. record debt for each of them according to their attribution

    unpayable_contributors = set(UnpayableContributorsRepo())
    payable_contributors = {
        email
        for email in distribution
        if email and email not in unpayable_contributors
    }

    #
    # Pay as many outstanding debts as possible
    #

    debt_payments = pay_outstanding_debts(
        payment.amount, DebtsRepo(), payable_contributors
    )

    # The "available" amount is what is left over after paying off debts
    available_amount = payment.amount - sum(dp.amount for dp in debt_payments)

    #
    # Create fresh debts for anyone we can't pay
    #
    # TODO: Make it clearer that some people get debts and the others
    # get N advances (maybe zero)

    fresh_debts = create_debts(
        available_amount, distribution, payable_contributors, payment
    )

    #
    # Draw dawn contributor's existing advances first, before paying them
    #

    negative_advances = draw_down_advances(
        available_amount, distribution, unpayable_contributors, payment
    )

    #
    # Advance payable contributors any extra money
    #

    fresh_advances = advance_payments(
        fresh_debts,
        negative_advances,
        distribution,
        unpayable_contributors,
        payment,
    )

    #
    # Create equity transactions for the total amounts of outgoing money
    #

    negative_advance_totals = Tally(
        (a.email, a.amount) for a in negative_advances
    )
    fresh_advance_totals = Tally((a.email, a.amount) for a in fresh_advances)
    debt_payments_totals = Tally(
        (dp.debt.email, dp.amount) for dp in debt_payments
    )

    transactions = [
        Transaction(
            email=email,
            payment_file=payment.file,
            amount=(
                # what you would normally get
                equity
                # minus amount drawn from your advances
                - abs(negative_advance_totals[email])
                # plus new advances from the pot
                + fresh_advance_totals[email]
                # plus any payments for old debts
                + debt_payments_totals[email]
            ),
        )
        for email, equity in distribution.distribute(available_amount).items()
        if email in payable_contributors
    ]

    processed_debts = fresh_debts
    advances = negative_advances + fresh_advances

    return processed_debts, debt_payments, transactions, advances


# TODO: the payments within a commit are not ordered.
# It may be better to sort them chronologically, so that
# earlier payments are reflected in attributions before
# later payments are processed.
def process_payments(instruments, attributions):
    """
    Process new payments by paying out instruments and then, from the amount
    left over, paying out attributions.
    Returns all newly created transactions and the updated valuation amount
    after all of the new payments have been processed.
    """
    price = read_price()
    valuation = read_valuation()
    new_debts = []
    new_debt_payments = []
    new_advances = []
    new_transactions = []
    new_itemized_payments = []

    processed_payment_files = {t.payment_file for t in TransactionsRepo()}
    unprocessed_payments = [
        p for p in AllPaymentsRepo() if p.file not in processed_payment_files
    ]

    for payment in unprocessed_payments:
        # first, process instruments (i.e. pay fees)
        debts, debt_payments, transactions, advances = distribute_payment(
            payment,
            Distribution(
                # The missing percentage in the instruments file
                # should not be distributed to anyone (shareholder: None)
                # TODO: Move to process_payments_and_record_updates
                {**instruments, None: Decimal(1) - sum(instruments.values())}
            ),
        )
        new_transactions += transactions
        new_debts += debts
        new_debt_payments += debt_payments
        new_advances += advances
        fees_paid_out = sum(t.amount for t in transactions)
        # deduct the amount paid out to instruments before
        # processing it for attributions
        payment.amount -= fees_paid_out
        new_itemized_payments.append(
            ItemizedPayment(
                payment.email,
                fees_paid_out,
                payment.amount,  # already has fees deducted
                payment.attributable,
                payment.file,
            )
        )
        # next, process attributions - using the amount owed to the project
        # (which is the amount leftover after paying instruments/fees)
        if payment.amount > ACCOUNTING_ZERO:
            debts, debt_payments, transactions, advances = distribute_payment(
                payment, Distribution(attributions)
            )
            new_transactions += transactions
            new_debts += debts
            new_debt_payments += debt_payments
            new_advances += advances
        if payment.attributable:
            valuation = handle_investment(
                payment, new_itemized_payments, attributions, price, valuation
            )

    debts = recalculate_debts(new_debts, new_debt_payments)

    return (
        debts,
        new_transactions,
        valuation,
        new_itemized_payments,
        new_advances,
    )


def process_payments_and_record_updates():
    """
    Allocate incoming payments to contributors according to the instruments
    and attributions files. Record updated transactions, valuation, and
    renormalized attributions only after all payments have been processed.
    """
    instruments = {a.email: a.decimal_share for a in InstrumentsRepo()}
    attributions = {a.email: a.decimal_share for a in AttributionsRepo()}

    assert_attributions_normalized(attributions)

    (
        debts,
        transactions,
        posterior_valuation,
        new_itemized_payments,
        advances,
    ) = process_payments(instruments, attributions)

    # we only write the changes to disk at the end
    # so that if any errors are encountered, no
    # changes are made.
    write_debts(debts)
    write_attributions(attributions)
    write_valuation(posterior_valuation)
    TransactionsRepo().extend(transactions)
    ItemizedPaymentsRepo().extend(new_itemized_payments)
    AdvancesRepo().extend(advances)
