from decimal import Decimal
from oldabe.money_in import (
    calculate_incoming_investment,
    total_amount_paid_to_project,
    calculate_incoming_attribution,
    generate_transactions,
    renormalize,
    inflate_valuation,
    process_payments,
)
from oldabe.accounting_utils import correct_rounding_error
from oldabe.models import Attribution, Payment
import pytest
from unittest.mock import patch
from .utils import call_sequence
from .fixtures import (
    instruments,
    normalized_attributions,
    excess_attributions,
    shortfall_attributions,
    empty_attributions,
    single_contributor_attributions,
    itemized_payments,
    new_itemized_payments,
)  # noqa


class TestGenerateTransactions:
    def test_zero_amount(self, normalized_attributions):
        with pytest.raises(AssertionError):
            generate_transactions(
                0, normalized_attributions, 'payment-1.txt', 'abc123'
            )

    def test_empty_attributions(self, empty_attributions):
        with pytest.raises(AssertionError):
            generate_transactions(
                100, empty_attributions, 'payment-1.txt', 'abc123'
            )

    def test_single_contributor_attributions(
        self, single_contributor_attributions
    ):
        amount = 100
        payment_file = 'payment-1.txt'
        commit_hash = 'abc123'
        result = generate_transactions(
            amount, single_contributor_attributions, payment_file, commit_hash
        )
        t = result[0]
        assert t.amount == amount

    def test_as_many_transactions_as_attributions(
        self, normalized_attributions
    ):
        amount = 100
        payment_file = 'payment-1.txt'
        commit_hash = 'abc123'
        result = generate_transactions(
            amount, normalized_attributions, payment_file, commit_hash
        )
        assert len(result) == len(normalized_attributions)

    def test_transactions_reflect_attributions(self, normalized_attributions):
        amount = 100
        payment_file = 'payment-1.txt'
        commit_hash = 'abc123'
        result = generate_transactions(
            amount, normalized_attributions, payment_file, commit_hash
        )
        for t in result:
            assert t.amount == normalized_attributions[t.email] * amount

    def test_everyone_in_attributions_are_represented(
        self, normalized_attributions
    ):
        amount = 100
        payment_file = 'payment-1.txt'
        commit_hash = 'abc123'
        result = generate_transactions(
            amount, normalized_attributions, payment_file, commit_hash
        )
        emails = [t.email for t in result]
        for contributor in normalized_attributions:
            assert contributor in emails

    def test_transaction_refers_to_payment(self, normalized_attributions):
        amount = 100
        payment_file = 'payment-1.txt'
        commit_hash = 'abc123'
        result = generate_transactions(
            amount, normalized_attributions, payment_file, commit_hash
        )
        t = result[0]
        assert t.payment_file == payment_file

    def test_transaction_refers_to_commit(self, normalized_attributions):
        amount = 100
        payment_file = 'payment-1.txt'
        commit_hash = 'abc123'
        result = generate_transactions(
            amount, normalized_attributions, payment_file, commit_hash
        )
        t = result[0]
        assert t.commit_hash == commit_hash


class TestProcessPayments:
    @patch('oldabe.money_in._get_unprocessed_payments')
    @patch('oldabe.money_in.get_all_payments')
    @patch('oldabe.money_in.read_valuation')
    @patch('oldabe.money_in.read_price')
    def test_collects_transactions_for_all_payments(
        self,
        mock_read_price,
        mock_read_valuation,
        mock_get_all_payments,
        mock_unprocessed_files,
        normalized_attributions,
        instruments,
    ):
        price = 100
        valuation = 1000
        payments = [
            Payment('a@b.com', 100, True),
            Payment('a@b.com', 200, False),
        ]
        mock_read_price.return_value = price
        mock_read_valuation.return_value = valuation
        mock_unprocessed_files.return_value = payments
        mock_get_all_payments.return_value = payments

        transactions, _, _ = process_payments(
            instruments, normalized_attributions
        )
        # generates a transaction for each payment and each contributor in the
        # attributions and instruments files
        expected_total = len(payments) * (
            len(normalized_attributions) + len(instruments)
        )
        assert len(transactions) == expected_total

    # def test_attributable_payments_update_valuation
    # def test_non_attributable_payments_do_not_update_valuation
    # def test_attributions_are_renormalized_by_attributable_payments
    # def test_instruments_are_not_renormalized_by_attributable_payments


class TestCalculateIncomingAttribution:
    def test_incoming_investment_less_than_zero(self, normalized_attributions):
        assert (
            calculate_incoming_attribution(
                'a@b.co', Decimal('-50'), Decimal('10000')
            )
            == None
        )

    def test_incoming_investment_is_zero(self, normalized_attributions):
        assert (
            calculate_incoming_attribution(
                'a@b.co', Decimal('0'), Decimal('10000')
            )
            == None
        )

    def test_normal_incoming_investment(self, normalized_attributions):
        assert calculate_incoming_attribution(
            'a@b.co', Decimal('50'), Decimal('10000')
        ) == Attribution(
            'a@b.co',
            Decimal('0.005'),
        )

    def test_large_incoming_investment(self, normalized_attributions):
        assert calculate_incoming_attribution(
            'a@b.co', Decimal('5000'), Decimal('10000')
        ) == Attribution(
            'a@b.co',
            Decimal('0.5'),
        )


class TestRenormalize:
    @pytest.mark.parametrize(
        "incoming_attribution, renormalized_attributions",
        [
            # new investor
            (
                Attribution('c@d.com', Decimal('0.05')),
                {
                    'a@b.com': Decimal('0.19'),
                    'b@c.com': Decimal('0.76'),
                    'c@d.com': Decimal('0.05'),
                },
            ),
            (
                Attribution('c@d.com', Decimal('0.5')),
                {
                    'a@b.com': Decimal('0.1'),
                    'b@c.com': Decimal('0.4'),
                    'c@d.com': Decimal('0.5'),
                },
            ),
            (
                Attribution('c@d.com', Decimal('0.7')),
                {
                    'a@b.com': Decimal('0.06'),
                    'b@c.com': Decimal('0.24'),
                    'c@d.com': Decimal('0.7'),
                },
            ),
            # existing investor
            (
                Attribution('b@c.com', Decimal('0.05')),
                {
                    'a@b.com': Decimal('0.19'),
                    'b@c.com': Decimal('0.81'),
                },
            ),
            (
                Attribution('b@c.com', Decimal('0.5')),
                {
                    'a@b.com': Decimal('0.1'),
                    'b@c.com': Decimal('0.9'),
                },
            ),
            (
                Attribution('b@c.com', Decimal('0.7')),
                {
                    'a@b.com': Decimal('0.06'),
                    'b@c.com': Decimal('0.94'),
                },
            ),
        ],
    )
    def test_matrix(
        self,
        incoming_attribution,
        renormalized_attributions,
        normalized_attributions,
    ):
        attributions = normalized_attributions
        renormalize(attributions, incoming_attribution)
        assert attributions == renormalized_attributions


class TestCorrectRoundingError:
    @pytest.mark.parametrize(
        "attributions, test_diff",
        [
            ("normalized_attributions", Decimal("0")),
            ("excess_attributions", Decimal("0")),
            ("shortfall_attributions", Decimal("0")),
            ("normalized_attributions", Decimal("0.1")),
            ("excess_attributions", Decimal("0.1")),
            ("shortfall_attributions", Decimal("0.1")),
            ("normalized_attributions", Decimal("-0.1")),
            ("excess_attributions", Decimal("-0.1")),
            ("shortfall_attributions", Decimal("-0.1")),
        ],
    )
    @patch('oldabe.money_in.get_rounding_difference')
    def test_incoming_is_adjusted_by_rounding_error(
        self, mock_rounding_difference, attributions, test_diff, request
    ):
        # Re: request, see: https://stackoverflow.com/q/42014484
        attributions = request.getfixturevalue(attributions)
        mock_rounding_difference.return_value = test_diff
        incoming_email = 'a@b.com'
        incoming_attribution = Attribution(
            incoming_email, attributions[incoming_email]
        )
        other_attributions = attributions.copy()
        other_attributions.pop(incoming_attribution.email)
        original_share = incoming_attribution.share
        correct_rounding_error(attributions, incoming_attribution)
        assert (
            attributions[incoming_attribution.email]
            == original_share - test_diff
        )

    @pytest.mark.parametrize(
        "attributions, test_diff",
        [
            ("normalized_attributions", Decimal("0")),
            ("excess_attributions", Decimal("0")),
            ("shortfall_attributions", Decimal("0")),
            ("normalized_attributions", Decimal("0.1")),
            ("excess_attributions", Decimal("0.1")),
            ("shortfall_attributions", Decimal("0.1")),
            ("normalized_attributions", Decimal("-0.1")),
            ("excess_attributions", Decimal("-0.1")),
            ("shortfall_attributions", Decimal("-0.1")),
        ],
    )
    @patch('oldabe.money_in.get_rounding_difference')
    def test_existing_attributions_are_unchanged(
        self, mock_rounding_difference, attributions, test_diff, request
    ):
        attributions = request.getfixturevalue(attributions)
        mock_rounding_difference.return_value = test_diff
        incoming_email = 'a@b.com'
        incoming_attribution = Attribution(
            incoming_email, attributions[incoming_email]
        )
        other_attributions = attributions.copy()
        other_attributions.pop(incoming_attribution.email)
        correct_rounding_error(attributions, incoming_attribution)
        attributions.pop(incoming_attribution.email)
        assert attributions == other_attributions


class TestInflateValuation:
    @patch('oldabe.money_in.open')
    def test_valuation_inflates_by_fresh_value(self, mock_open):
        amount = 100
        valuation = 1000
        new_valuation = inflate_valuation(valuation, amount)
        assert new_valuation == amount + valuation


class TotalAmountPaidToProject:
    @patch('oldabe.money_in.get_existing_itemized_payments')
    def test_total_amount_for_a_all_attributable(
        self,
        get_existing_itemized_payments,
        itemized_payments,
        new_itemized_payments,
    ):
        get_existing_itemized_payments.return_value = itemized_payments
        total = total_amount_paid_to_project('a@b.com', new_itemized_payments)
        assert total == 194

    @patch('oldabe.money_in.get_existing_itemized_payments')
    def test_total_amount_for_c_one_non_attributable(
        self,
        get_existing_itemized_payments,
        itemized_payments,
        new_itemized_payments,
    ):
        get_existing_itemized_payments.return_value = itemized_payments
        total = total_amount_paid_to_project('c@d.com', new_itemized_payments)
        assert total == 30


class TestCalculateIncomingInvestment:
    @pytest.mark.parametrize(
        "prior_contribution, incoming_amount, price, expected_investment",
        [
            (Decimal("0"), Decimal("0"), Decimal("100"), Decimal("0")),
            (Decimal("0"), Decimal("20"), Decimal("100"), Decimal("0")),
            (Decimal("0"), Decimal("100"), Decimal("100"), Decimal("0")),
            (Decimal("0"), Decimal("120"), Decimal("100"), Decimal("20")),
            (Decimal("20"), Decimal("0"), Decimal("100"), Decimal("0")),
            (Decimal("20"), Decimal("20"), Decimal("100"), Decimal("0")),
            (Decimal("20"), Decimal("80"), Decimal("100"), Decimal("0")),
            (Decimal("20"), Decimal("100"), Decimal("100"), Decimal("20")),
            (Decimal("100"), Decimal("0"), Decimal("100"), Decimal("0")),
            (Decimal("100"), Decimal("20"), Decimal("100"), Decimal("20")),
            (Decimal("120"), Decimal("0"), Decimal("100"), Decimal("0")),
            (Decimal("120"), Decimal("20"), Decimal("100"), Decimal("20")),
        ],
    )
    @patch('oldabe.money_in.total_amount_paid_to_project')
    def test_matrix(
        self,
        total_amount_paid_to_project,
        prior_contribution,
        incoming_amount,
        price,
        expected_investment,
    ):
        email = 'dummy@abe.org'
        payment = Payment(email, incoming_amount)
        # this is the total amount paid _including_ the incoming amount
        total_amount_paid_to_project.return_value = (
            prior_contribution + incoming_amount
        )
        result = calculate_incoming_investment(payment, price, [])
        assert result == expected_investment
