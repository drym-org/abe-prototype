import os
from datetime import datetime
from decimal import localcontext
from unittest.mock import patch

import pytest
import time_machine

from oldabe.money_in import process_payments_and_record_updates
from oldabe.money_out import compile_outstanding_balances

from .fixtures import abe_fs


class TestNoPayments:

    @patch('oldabe.models.default_commit_hash', return_value='abcd123')
    def test_no_transactions_generated(self, mock_git_rev, abe_fs):
        process_payments_and_record_updates()
        with open('./abe/transactions.txt') as f:
            assert f.read() == ""

    @patch('oldabe.models.default_commit_hash', return_value='abcd123')
    def test_compiled_outstanding_balances(self, mock_git_rev, abe_fs):
        process_payments_and_record_updates()
        message = compile_outstanding_balances()
        assert "There are no outstanding (payable) balances." in message
        assert "There are no outstanding (unpayable) debts." in message
        assert "There are no advances." in message


# TODO: in some cases even though the value is e.g. 1,
# it's writing out 3 decimal places, like 1.000. We should
# figure out why this is happening (and whether it's OK)
# and decide on appropriate handling


class TestPaymentAbovePrice:

    @time_machine.travel(datetime(1985, 10, 26, 1, 24), tick=False)
    @patch('oldabe.models.default_commit_hash', return_value='abcd123')
    def test_generates_transactions(self, mock_git_rev, abe_fs):
        with localcontext() as context:
            context.prec = 2
            amount = 100
            abe_fs.create_file(
                "./abe/payments/1.txt",
                contents=f"sam,036eaf6,{amount},1987-06-30 06:25:00",
            )
            process_payments_and_record_updates()
            with open('./abe/transactions.txt') as f:
                assert f.read() == (
                    "old abe,1.0,1.txt,abcd123,1985-10-26 01:24:00\n"
                    "DIA,5.0,1.txt,abcd123,1985-10-26 01:24:00\n"
                    "sid,47,1.txt,abcd123,1985-10-26 01:24:00\n"
                    "jair,28,1.txt,abcd123,1985-10-26 01:24:00\n"
                    "ariana,19,1.txt,abcd123,1985-10-26 01:24:00\n"
                )

    @time_machine.travel(datetime(1985, 10, 26, 1, 24), tick=False)
    @patch('oldabe.models.default_commit_hash', return_value='abcd123')
    def test_dilutes_attributions(self, mock_git_rev, abe_fs):
        with localcontext() as context:
            context.prec = 2
            amount = 10000
            abe_fs.create_file(
                "./abe/payments/1.txt",
                contents=f"sam,036eaf6,{amount},1987-06-30 06:25:00",
            )
            process_payments_and_record_updates()
            with open('./abe/attributions.txt') as f:
                assert f.read() == (
                    "sid,46\n" "jair,28\n" "ariana,18\n" "sam,8.5\n"
                )

    @time_machine.travel(datetime(1985, 10, 26, 1, 24), tick=False)
    @patch('oldabe.models.default_commit_hash', return_value='abcd123')
    def test_compiled_outstanding_balances(self, mock_git_rev, abe_fs):
        with localcontext() as context:
            context.prec = 2
            amount = 100
            abe_fs.create_file(
                "./abe/payments/1.txt",
                contents=f"sam,036eaf6,{amount},1987-06-30 06:25:00",
            )
            process_payments_and_record_updates()

            message = compile_outstanding_balances()

            assert (
                "| Name | Balance |\r\n"
                "| ---- | --- |\r\n"
                "old abe | 1.00\r\n"
            ) in message


class TestPaymentBelowPrice:

    @time_machine.travel(datetime(1985, 10, 26, 1, 24), tick=False)
    @patch('oldabe.models.default_commit_hash', return_value='abcd123')
    def test_generates_transactions(self, mock_git_rev, abe_fs):
        with localcontext() as context:
            context.prec = 2
            amount = 1
            abe_fs.create_file(
                "./abe/payments/1.txt",
                contents=f"sam,036eaf6,{amount},1987-06-30 06:25:00",
            )
            process_payments_and_record_updates()
            with open('./abe/transactions.txt') as f:
                assert f.read() == (
                    "old abe,0.010,1.txt,abcd123,1985-10-26 01:24:00\n"
                    "DIA,0.050,1.txt,abcd123,1985-10-26 01:24:00\n"
                    "sid,0.47,1.txt,abcd123,1985-10-26 01:24:00\n"
                    "jair,0.28,1.txt,abcd123,1985-10-26 01:24:00\n"
                    "ariana,0.19,1.txt,abcd123,1985-10-26 01:24:00\n"
                )

    @time_machine.travel(datetime(1985, 10, 26, 1, 24), tick=False)
    @patch('oldabe.models.default_commit_hash', return_value='abcd123')
    def test_compiled_outstanding_balances(self, mock_git_rev, abe_fs):
        with localcontext() as context:
            context.prec = 2
            amount = 1
            abe_fs.create_file(
                "./abe/payments/1.txt",
                contents=f"sam,036eaf6,{amount},1987-06-30 06:25:00",
            )
            process_payments_and_record_updates()
            message = compile_outstanding_balances()

            assert (
                "| Name | Balance |\r\n"
                "| ---- | --- |\r\n"
                "old abe | 0.01\r\n"
            ) in message


class TestNonAttributablePayment:

    @time_machine.travel(datetime(1985, 10, 26, 1, 24), tick=False)
    @patch('oldabe.models.default_commit_hash', return_value='abcd123')
    def test_does_not_dilute_attributions(self, mock_git_rev, abe_fs):
        with localcontext() as context:
            context.prec = 2
            amount = 100
            abe_fs.create_file(
                "./abe/payments/nonattributable/1.txt",
                contents=f"sam,036eaf6,{amount},1987-06-30 06:25:00",
            )
            process_payments_and_record_updates()
            with open('./abe/attributions.txt') as f:
                assert f.read() == ("sid,50\n" "jair,30\n" "ariana,20\n")

    @time_machine.travel(datetime(1985, 10, 26, 1, 24), tick=False)
    @patch('oldabe.models.default_commit_hash', return_value='abcd123')
    def test_generates_transactions(self, mock_git_rev, abe_fs):
        with localcontext() as context:
            context.prec = 2
            amount = 100
            abe_fs.create_file(
                "./abe/payments/1.txt",
                contents=f"sam,036eaf6,{amount},1987-06-30 06:25:00",
            )
            process_payments_and_record_updates()
            with open('./abe/transactions.txt') as f:
                assert f.read() == (
                    "old abe,1.0,1.txt,abcd123,1985-10-26 01:24:00\n"
                    "DIA,5.0,1.txt,abcd123,1985-10-26 01:24:00\n"
                    "sid,47,1.txt,abcd123,1985-10-26 01:24:00\n"
                    "jair,28,1.txt,abcd123,1985-10-26 01:24:00\n"
                    "ariana,19,1.txt,abcd123,1985-10-26 01:24:00\n"
                )

    @time_machine.travel(datetime(1985, 10, 26, 1, 24), tick=False)
    @patch('oldabe.models.default_commit_hash', return_value='abcd123')
    def test_compiled_outstanding_balances(self, mock_git_rev, abe_fs):
        with localcontext() as context:
            context.prec = 2
            amount = 100
            abe_fs.create_file(
                "./abe/payments/nonattributable/1.txt",
                contents=f"sam,036eaf6,{amount},1987-06-30 06:25:00",
            )
            process_payments_and_record_updates()
            message = compile_outstanding_balances()

            assert (
                "| Name | Balance |\r\n"
                "| ---- | --- |\r\n"
                "old abe | 1.00\r\n"
            ) in message


class TestMultiplePayments:

    # TODO: implement me
    @time_machine.travel(datetime(1985, 10, 26, 1, 24), tick=False)
    @patch('oldabe.models.default_commit_hash', return_value='abcd123')
    def test_generates_transactions(self, mock_git_rev, abe_fs):
        pass

    @time_machine.travel(datetime(1985, 10, 26, 1, 24), tick=False)
    @patch('oldabe.models.default_commit_hash', return_value='abcd123')
    def test_dilutes_attributions(self, mock_git_rev, abe_fs):
        with localcontext() as context:
            context.prec = 2
            amount = 10000
            abe_fs.create_file(
                "./abe/payments/1.txt",
                contents=f"sam,036eaf6,{amount},1987-06-30 06:25:00",
            )
            abe_fs.create_file(
                "./abe/payments/2.txt",
                contents=f"sam,036eaf6,{amount},1987-06-30 06:24:00",
            )
            process_payments_and_record_updates()
            with open('./abe/attributions.txt') as f:
                assert f.read() == (
                    "sid,42\n" "jair,26\n" "ariana,17\n" "sam,16\n"
                )

    # TODO: why do sam and sri not get into attributions when the amount
    # is 1000? For higher amounts like 10000 it seems OK
    # TODO: add a test to check that, even though both sam and sri get
    # attributed equally, sam gets paid from sri's payment,
    # but sri doesn't get paid from sam's, assuming sam is first
    @time_machine.travel(datetime(1985, 10, 26, 1, 24), tick=False)
    @patch('oldabe.models.default_commit_hash', return_value='abcd123')
    def test_equal_payment_results_in_equal_share(self, mock_git_rev, abe_fs):
        with localcontext() as context:
            context.prec = 2
            amount = 10000
            abe_fs.create_file(
                "./abe/payments/1.txt",
                contents=f"sam,036eaf6,{amount},1987-06-30 06:25:00",
            )
            abe_fs.create_file(
                "./abe/payments/2.txt",
                contents=f"sri,b36eaf6,{amount},1987-06-30 06:24:00",
            )
            process_payments_and_record_updates()
            with open('./abe/attributions.txt') as f:
                assert f.read() == (
                    "sid,42\n" "jair,26\n" "ariana,17\n" "sam,7.8\n" "sri,7.8\n"
                )

    # TODO: implement me
    @time_machine.travel(datetime(1985, 10, 26, 1, 24), tick=False)
    @patch('oldabe.models.default_commit_hash', return_value='abcd123')
    def test_compiled_outstanding_balances(self, mock_git_rev, abe_fs):
        pass


class TestUnpayableContributor:

    def _call(self, abe_fs):
        with localcontext() as context:
            context.prec = 2
            amount = 100
            abe_fs.create_file(
                "./abe/payments/1.txt",
                contents=f"sam,036eaf6,{amount},1987-06-30 06:25:00",
            )
            abe_fs.create_file(
                "./abe/unpayable_contributors.txt", contents=f"ariana"
            )
            process_payments_and_record_updates()

    @time_machine.travel(datetime(1985, 10, 26, 1, 24), tick=False)
    @patch('oldabe.models.default_commit_hash', return_value='abcd123')
    def test_generates_transactions(self, mock_git_rev, abe_fs):
        self._call(abe_fs)
        with open('./abe/transactions.txt') as f:
            assert f.read() == (
                "old abe,1.0,1.txt,abcd123,1985-10-26 01:24:00\n"
                "DIA,5.0,1.txt,abcd123,1985-10-26 01:24:00\n"
                "sid,58,1.txt,abcd123,1985-10-26 01:24:00\n"
                "jair,35,1.txt,abcd123,1985-10-26 01:24:00\n"
            )

    @time_machine.travel(datetime(1985, 10, 26, 1, 24), tick=False)
    @patch('oldabe.models.default_commit_hash', return_value='abcd123')
    def test_records_debt(self, mock_git_rev, abe_fs):
        self._call(abe_fs)
        with open('./abe/debts.txt') as f:
            assert f.read() == (
                "ariana,19,0,1.txt,abcd123,1985-10-26 01:24:00\n"
            )

    @time_machine.travel(datetime(1985, 10, 26, 1, 24), tick=False)
    @patch('oldabe.models.default_commit_hash', return_value='abcd123')
    def test_records_advances(self, mock_git_rev, abe_fs):
        # advances for payable people
        # and none for unpayable
        self._call(abe_fs)
        with open('./abe/advances.txt') as f:
            assert f.read() == (
                "sid,11,1.txt,abcd123,1985-10-26 01:24:00\n"
                "jair,6.8,1.txt,abcd123,1985-10-26 01:24:00\n"
            )

    @time_machine.travel(datetime(1985, 10, 26, 1, 24), tick=False)
    @patch('oldabe.models.default_commit_hash', return_value='abcd123')
    def test_compiled_outstanding_balances(self, mock_git_rev, abe_fs):
        self._call(abe_fs)
        message = compile_outstanding_balances()
        assert (
            "| Name | Debt |\r\n" "| ---- | --- |\r\n" "ariana | 19.00\r\n"
        ) in message


class TestUnpayableContributorBecomesPayable:

    def _call(self, abe_fs):
        with localcontext() as context:
            context.prec = 2
            amount = 100
            abe_fs.create_file(
                './abe/transactions.txt',
                contents=(
                    "old abe,1.0,1.txt,abcd123,1985-10-26 01:24:00\n"
                    "DIA,5.0,1.txt,abcd123,1985-10-26 01:24:00\n"
                    "sid,58,1.txt,abcd123,1985-10-26 01:24:00\n"
                    "jair,35,1.txt,abcd123,1985-10-26 01:24:00\n"
                ),
            )

            abe_fs.create_file(
                "./abe/debts.txt",
                contents="ariana,19,0,1.txt,abcd123,1985-10-26 01:24:00\n",
            )
            abe_fs.create_file(
                "./abe/advances.txt",
                contents=(
                    "sid,11,1.txt,abcd123,1985-10-26 01:24:00\n"
                    "jair,6.8,1.txt,abcd123,1985-10-26 01:24:00\n"
                ),
            )
            abe_fs.create_file(
                "./abe/payments/1.txt",
                contents=f"sam,036eaf6,{amount},1987-06-30 06:25:00",
            )
            abe_fs.create_file(
                "./abe/payments/2.txt",
                contents=f"sam,036eaf6,{amount},1987-06-30 06:25:00",
            )
            process_payments_and_record_updates()

    @time_machine.travel(datetime(1985, 10, 26, 1, 24), tick=False)
    @patch('oldabe.models.default_commit_hash', return_value='abcd123')
    def test_debt_paid(self, mock_git_rev, abe_fs):
        self._call(abe_fs)
        with open('./abe/debts.txt') as f:
            assert f.read() == (
                "ariana,19,19,1.txt,abcd123,1985-10-26 01:24:00\n"
            )

    @time_machine.travel(datetime(1985, 10, 26, 1, 24), tick=False)
    @patch('oldabe.models.default_commit_hash', return_value='abcd123')
    def test_transactions(self, mock_git_rev, abe_fs):
        # here, because the two payment amounts are the same,
        # it ends up correcting immediately. We might consider
        # more tests where the second amount is larger, or
        # where there are more debts
        self._call(abe_fs)
        with open('./abe/transactions.txt') as f:
            assert f.read() == (
                "old abe,1.0,1.txt,abcd123,1985-10-26 01:24:00\n"
                "DIA,5.0,1.txt,abcd123,1985-10-26 01:24:00\n"
                "sid,58,1.txt,abcd123,1985-10-26 01:24:00\n"
                "jair,35,1.txt,abcd123,1985-10-26 01:24:00\n"
                "old abe,1.0,2.txt,abcd123,1985-10-26 01:24:00\n"
                "DIA,5.0,2.txt,abcd123,1985-10-26 01:24:00\n"
                "sid,36,2.txt,abcd123,1985-10-26 01:24:00\n"
                "jair,20,2.txt,abcd123,1985-10-26 01:24:00\n"
                "ariana,38,2.txt,abcd123,1985-10-26 01:24:00\n"
            )

    @time_machine.travel(datetime(1985, 10, 26, 1, 24), tick=False)
    @patch('oldabe.models.default_commit_hash', return_value='abcd123')
    def test_advances(self, mock_git_rev, abe_fs):
        self._call(abe_fs)
        with open('./abe/advances.txt') as f:
            assert f.read() == (
                "sid,11,1.txt,abcd123,1985-10-26 01:24:00\n"
                "jair,6.8,1.txt,abcd123,1985-10-26 01:24:00\n"
                "sid,-11,2.txt,abcd123,1985-10-26 01:24:00\n"
                "jair,-6.8,2.txt,abcd123,1985-10-26 01:24:00\n"
                "sid,9.0,2.txt,abcd123,1985-10-26 01:24:00\n"
                "jair,5.4,2.txt,abcd123,1985-10-26 01:24:00\n"
                "ariana,3.6,2.txt,abcd123,1985-10-26 01:24:00\n"
            )

    @time_machine.travel(datetime(1985, 10, 26, 1, 24), tick=False)
    @patch('oldabe.models.default_commit_hash', return_value='abcd123')
    def test_compiled_outstanding_balances(self, mock_git_rev, abe_fs):
        self._call(abe_fs)
        message = compile_outstanding_balances()
        assert (
            "| Name | Debt |\r\n" "| ---- | --- |\r\n" "ariana | 0.00\r\n"
        ) in message
