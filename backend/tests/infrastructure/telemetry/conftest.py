import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader


@pytest.fixture
def metric_reader() -> InMemoryMetricReader:
    return InMemoryMetricReader()


@pytest.fixture
def meter(metric_reader):
    """A meter of its own, so tests never touch the global provider."""
    return MeterProvider(metric_readers=[metric_reader]).get_meter("test")


@pytest.fixture
def read_points(metric_reader):
    """Return `[(attributes, data point)]` of one metric, by name."""

    def read(name):
        data = metric_reader.get_metrics_data()
        if None is data:
            return []
        return [
            (dict(point.attributes), point)
            for resource_metrics in data.resource_metrics
            for scope_metrics in resource_metrics.scope_metrics
            for metric in scope_metrics.metrics
            if name == metric.name
            for point in metric.data.data_points
        ]

    return read
