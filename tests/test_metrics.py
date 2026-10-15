import unittest
from unittest.mock import Mock, patch

from sfx_olly.cli.main import build_parser
from sfx_olly.exceptions import SignalFlowError
from sfx_olly.help import topic_names
from sfx_olly.metrics import MetadataAPI, MetricQuery, SignalFlowAPI, SignalFlowMessage, build_program


class MetricInspectionTests(unittest.TestCase):
    def test_dimension_values_are_deduplicated_sorted_and_bounded(self):
        http = Mock()
        http.get_json.return_value = {
            "count": 3,
            "results": [
                {"dimensions": {"environment": "test", "host.name": "b", "sf_metric": None}},
                {"dimensions": {"environment": "test", "host.name": "a"}},
            ],
        }
        report = MetadataAPI(http).inspect_metric("example.project.size", limit=2)
        self.assertEqual(report["dimensions"], {"environment": ["test"], "host.name": ["a", "b"]})
        self.assertEqual(report["matched_series"], 3)
        self.assertEqual(report["inspected_series"], 2)
        self.assertTrue(report["truncated"])
        http.get_json.assert_called_once_with(
            "/v2/metrictimeseries",
            {"query": 'sf_metric:"example.project.size"', "limit": 2, "offset": 0},
        )

    def test_absent_metric_has_no_dimension_values(self):
        http = Mock()
        http.get_json.return_value = {"count": 0, "results": []}
        report = MetadataAPI(http).inspect_metric("missing.metric")
        self.assertEqual(report["dimensions"], {})
        self.assertEqual(report["matched_series"], 0)
        self.assertFalse(report["truncated"])

    def test_invalid_limit_does_not_call_api(self):
        http = Mock()
        with self.assertRaises(ValueError):
            MetadataAPI(http).inspect_metric("metric", limit=10_001)
        http.get_json.assert_not_called()


class MetricQueryTests(unittest.TestCase):
    def test_reported_query_preserves_dotted_dimension_name(self):
        program = build_program(MetricQuery(
            "example.project.size",
            filters={"deployment.environment.name": ["env-test"]},
        ))
        self.assertEqual(program,
            "data('example.project.size', filter=filter('deployment.environment.name', "
            "'env-test')).publish(label='A')")

    def test_queries_support_multiple_metrics(self):
        for metric in ("cpu.utilization", "example.project.size", "example.bytes.total"):
            with self.subTest(metric=metric):
                self.assertEqual(build_program(MetricQuery(metric)), f"data('{metric}').publish(label='A')")

    def test_filter_code_injection_is_rejected(self):
        with self.assertRaises(ValueError):
            build_program(MetricQuery("metric", filters={"host": ["bad'value"]}))


class SignalFlowTests(unittest.TestCase):
    def test_aborted_computation_is_not_reported_as_empty_data(self):
        api = SignalFlowAPI(Mock())
        api.stream = Mock(return_value=iter([
            SignalFlowMessage("control-message", {"event": "CHANNEL_ABORT", "abortInfo": "failed"}),
        ]))
        with self.assertRaisesRegex(SignalFlowError, "failed"):
            api.execute("data('metric').publish()", 0, 60_000)

    def test_metadata_is_joined_to_data(self):
        api = SignalFlowAPI(Mock())
        api.stream = Mock(return_value=iter([
            SignalFlowMessage("metadata", {"tsId": "series", "properties": {"environment": "test"}}),
            SignalFlowMessage("data", {"logicalTimestampMs": 1_000, "data": [{"tsId": "series", "value": 12}]}),
            SignalFlowMessage("control-message", {"event": "END_OF_CHANNEL"}),
        ]))
        points = api.execute("data('metric').publish()", 0, 60_000)
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0].value, 12)
        self.assertEqual(points[0].properties, {"environment": "test"})


class CLIWorkflowTests(unittest.TestCase):
    def test_watcher_is_removed(self):
        parser = build_parser()
        self.assertNotIn("watch", parser._subparsers._group_actions[0].choices)
        self.assertNotIn("watch", topic_names())

    @patch("sfx_olly.cli.data.error_console")
    @patch("sfx_olly.cli.data.emit")
    @patch("sfx_olly.cli.data.SplunkOllyClient")
    def test_empty_query_keeps_json_output_clean(self, client_class, emit, error_console):
        client_class.return_value.__enter__.return_value.signalflow.execute.return_value = []
        args = build_parser().parse_args(["-o", "json", "query", "example.project.size"])
        self.assertEqual(args.handler(args), 0)
        self.assertEqual(emit.call_args.args[:2], ("json", []))
        self.assertIn("metrics inspect example.project.size", str(error_console.print.call_args.args[0]))

    @patch("sfx_olly.cli.metadata.print_json")
    @patch("sfx_olly.cli.metadata.SplunkOllyClient")
    def test_inspection_supports_json(self, client_class, print_json):
        report = {"metric": "metric", "dimensions": {"environment": ["test"]}}
        client_class.return_value.__enter__.return_value.metadata.inspect_metric.return_value = report
        args = build_parser().parse_args(["-o", "json", "metrics", "inspect", "metric"])
        self.assertEqual(args.handler(args), 0)
        print_json.assert_called_once_with(report)