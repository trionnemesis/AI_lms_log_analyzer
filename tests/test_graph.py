from unittest import TestCase
from lms_log_analyzer.src.graph_builder import GraphBuilder
from lms_log_analyzer.src.graph_retrieval_tool import GraphRetrievalTool

class TestGraphModules(TestCase):
    def test_builder_methods_noop_without_graph(self):
        builder = GraphBuilder(uri="bolt://invalid:7687")
        builder.graph = None  # ensure no connection
        # Should not raise when graph is unavailable
        builder.create_entities([{"id": "e1", "label": "IP"}])
        builder.create_relations([
            {"start_id": "e1", "end_id": "e2", "type": "RELATED"}
        ])

    def test_retrieval_empty_without_graph(self):
        builder = GraphBuilder(uri="bolt://invalid:7687")
        builder.graph = None
        tool = GraphRetrievalTool(builder)
        result = tool.retrieve_for_line("Failed login from 1.1.1.1 user=root")
        self.assertEqual(result, {"nodes": [], "relationships": []})
