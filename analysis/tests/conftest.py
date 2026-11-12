"""Keep Matplotlib figures from accumulating between analysis tests."""

import matplotlib.pyplot as plt
import pytest


@pytest.fixture(autouse=True)
def close_figures_around_each_test():
    """Recipe tests inspect returned figures but do not own the global registry."""
    plt.close("all")
    yield
    plt.close("all")
