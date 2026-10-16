from app.services.business_knowledge_layer import BUSINESS_METRICS, BUSINESS_OBJECTS, BusinessKnowledgeLayer


class ReportSemanticValidator:
    def __init__(self, knowledge=None):
        self.knowledge = knowledge or BusinessKnowledgeLayer()

    def evaluate(self, intent) -> tuple[list[str], list[dict]]:
        unavailable = []
        for object_id in intent.objects:
            if BUSINESS_OBJECTS.get(object_id, {}).get("planned"):
                unavailable.append(object_id)
        for metric_id in intent.metrics:
            metric = BUSINESS_METRICS.get(metric_id)
            if not metric or metric.get("planned") or not metric.get("definition"):
                unavailable.append(metric_id)
        validation = self.knowledge.validate(objects=intent.objects, metrics=intent.metrics, dimensions=intent.dimensions)
        ambiguities = [item for item in validation["warnings"] if item["code"] == "AMBIGUOUS_DIMENSION"]
        return sorted(set(unavailable)), ambiguities

    @staticmethod
    def questions(ambiguities: list[dict]) -> list[dict]:
        questions = []
        for warning in ambiguities:
            concept = warning["concept"]
            questions.append({
                "id": f"{concept}_context",
                "question": f"Qual {BUSINESS_OBJECTS[concept]['name'].lower()} você deseja utilizar?",
                "options": [
                    {"value": f"{owner}_{concept}", "label": f"{BUSINESS_OBJECTS[concept]['name']} do {BUSINESS_OBJECTS[owner]['name'].lower()}"}
                    for owner in warning["options"]
                ],
            })
        return questions
