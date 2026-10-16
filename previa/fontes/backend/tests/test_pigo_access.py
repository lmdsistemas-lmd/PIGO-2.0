import unittest
from fastapi import HTTPException
from pydantic import ValidationError
from app.ai.validators.permission_validator import ReportPermissionValidator, ReportPermissionError
from app.routes.pigo_access import ProfileInput
from app.services.pigo_access_service import check_permission, validate_permissions


class PigoPermissionTests(unittest.TestCase):
    def test_profile_permission_is_enforced_on_direct_api_urls_and_writes(self):
        reader={'permissions':['catalogs.read']}
        check_permission(reader,'/api/operacoes/clientes','GET')
        for path,method in [('/api/acesso/usuarios','GET'),('/api/operacoes/fechamentos/1/export','GET'),('/api/erp/cadastros/clientes','POST'),('/api/unknown','GET')]:
            with self.subTest(path=path), self.assertRaises(HTTPException) as error:check_permission(reader,path,method)
            self.assertEqual(error.exception.status_code,403)

    def test_finance_sources_cannot_be_unlocked_by_an_unrelated_manage_permission(self):
        user={'auth_source':'pigo','role':'administrator','permissions':['reports.read','catalogs.manage']}
        with self.assertRaises(ReportPermissionError):ReportPermissionValidator().validate('finance',user)
        ReportPermissionValidator().validate('finance',{**user,'permissions':['finance.read']})

    def test_profile_names_are_trimmed_before_length_validation_and_permissions_are_allowlisted(self):
        with self.assertRaises(ValidationError):ProfileInput(nome='   ')
        with self.assertRaises(HTTPException):validate_permissions(['all'])
        self.assertEqual(validate_permissions(['team.read','team.read']),['team.read'])
