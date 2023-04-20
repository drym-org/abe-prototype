from decimal import Decimal
import pytest


@pytest.fixture
def normalized_attributions():
    return {'a@b.com': Decimal("0.2"), 'b@c.com': Decimal("0.8")}


@pytest.fixture
def excess_attributions():
    return {'a@b.com': Decimal("0.2"), 'b@c.com': Decimal("0.9")}


@pytest.fixture
def shortfall_attributions():
    return {'a@b.com': Decimal("0.2"), 'b@c.com': Decimal("0.7")}


@pytest.fixture
def empty_attributions():
    return {}


@pytest.fixture
def single_contributor_attributions():
    return {'a@b.com': Decimal("1")}
