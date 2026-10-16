import unittest

from app.services.business_knowledge_layer import BusinessKnowledgeLayer


class BusinessKnowledgeLayerTests(unittest.TestCase):
    def setUp(self):
        self.knowledge = BusinessKnowledgeLayer()

    def test_public_model_contains_no_physical_identifiers(self):
        model = str(self.knowledge.public_model()).upper()
        for physical_prefix in ("TB_", "PEV_", "REC_", "JOIN ", "SELECT "):
            self.assertNotIn(physical_prefix, model)

    def test_core_objects_relations_and_metrics_are_registered(self):
        model = self.knowledge.public_model()
        self.assertIn("sale", model["objects"])
        self.assertIn("customer", model["objects"])
        self.assertIn({"from": "sale", "to": "customer", "cardinality": "many_to_one"}, model["relations"])
        self.assertEqual(model["metrics"]["revenue"]["definition"]["aggregation"], "sum")

    def test_validator_rejects_planned_and_unknown_concepts(self):
        result = self.knowledge.validate(objects=["payment"], metrics=["unknown"])
        self.assertFalse(result["valid"])
        self.assertEqual({error["code"] for error in result["errors"]}, {"OBJECT_NOT_AVAILABLE", "UNKNOWN_METRIC"})

    def test_validator_reports_ambiguous_city(self):
        result = self.knowledge.validate(metrics=["revenue"], dimensions=["city"])
        self.assertFalse(result["valid"])
        self.assertEqual(result["warnings"][0]["code"], "AMBIGUOUS_DIMENSION")
        self.assertEqual(result["warnings"][0]["options"], ["customer", "seller"])

    def test_intent_parser_uses_business_language_only(self):
        result = self.knowledge.parse_intent("Quero o faturamento por vendedor do último trimestre")
        self.assertEqual(result["intent"]["metrics"], ["revenue"])
        self.assertIn("seller", result["intent"]["dimensions"])
        self.assertEqual(result["intent"]["period"], "last_quarter")
        self.assertNotIn("sql", str(result).lower())


if __name__ == "__main__":
    unittest.main()
