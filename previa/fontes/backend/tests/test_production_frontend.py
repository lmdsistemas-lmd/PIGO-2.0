import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.main import app


class ProductionFrontendTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "index.html").write_text("<!doctype html><html><body>PIGO shell</body></html>")
        self.patch = patch("app.main.FRONTEND_DIST_DIR", self.root)
        self.patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.patch.stop()
        self.directory.cleanup()

    def test_direct_navigation_and_refresh_load_react_shell(self):
        for path in ["/", "/login", "/dashboard/vendas", "/dashboard/estoque", "/funcionarios", "/performance", "/relatorios", "/cadastros/produtos"]:
            with self.subTest(path=path):
                response = self.client.get(path, headers={"Accept": "text/html"})
                self.assertEqual(response.status_code, 200)
                self.assertIn("PIGO shell", response.text)

    def test_html_accept_cannot_bypass_api_authentication(self):
        for path in ["/api/operacoes/produtos?empresa_id=1", "/api/erp/cadastros/clientes?empresa_id=1", "/api/dashboard/clientes?empresa_id=1"]:
            with self.subTest(path=path):
                response = self.client.get(path, headers={"Accept": "text/html"})
                self.assertEqual(response.status_code, 401)
                self.assertNotIn("PIGO shell", response.text)

    def test_unknown_api_and_assets_do_not_return_html_shell(self):
        for path in ["/api", "/api/nonexistent", "/assets/nonexistent.js", "/docs/nonexistent"]:
            with self.subTest(path=path):
                response = self.client.get(path, headers={"Accept": "text/html"})
                self.assertEqual(response.status_code, 404)
                self.assertNotIn("PIGO shell", response.text)
