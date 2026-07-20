import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { listarEmpresas, obterTenantAtual } from "../services/empresaService";
import { useAuth } from "./AuthContext";

const EmpresaContext = createContext(null);

export function EmpresaProvider({ children }) {
  const { isAuthenticated, loadingAuth } = useAuth();

  const [empresas, setEmpresas] = useState([]);
  const [empresaAtual, setEmpresaAtual] = useState(() => {
    const saved = localStorage.getItem("empresa_atual");
    return saved ? JSON.parse(saved) : null;
  });
  const [loadingEmpresas, setLoadingEmpresas] = useState(false);

  useEffect(() => {
    async function carregarEmpresas() {
      try {
        setLoadingEmpresas(true);

        const [tenantAtual, data] = await Promise.all([
          obterTenantAtual().catch((error) => {
            console.warn("[DEBUG EMPRESA CONTEXT] Tenant atual indisponivel:", error);
            return null;
          }),
          listarEmpresas(),
        ]);
        const lista = Array.isArray(data) ? data : [];
        const tenantEmpresa = tenantAtual
          ? {
              id: null,
              selector_id: "tenant",
              tenant_id: tenantAtual.tenant_id,
              fantasia: tenantAtual.nome_fantasia || "",
              razao_social: tenantAtual.razao_social || "",
              cnpj: tenantAtual.cnpj || "",
              cidade: "",
              status: tenantAtual.has_pigo_access ? "ATIVO" : "INATIVO",
              nome_exibicao:
                tenantAtual.display_name ||
                tenantAtual.nome_fantasia ||
                tenantAtual.razao_social ||
                tenantAtual.cnpj,
              isTenantContext: true,
            }
          : null;

        const listaComTenant = lista.length
          ? lista.map((empresa, index) =>
              index === 0 && tenantEmpresa
                ? {
                    ...empresa,
                    selector_id: String(empresa.id),
                    tenant_id: tenantEmpresa.tenant_id,
                    fantasia: tenantEmpresa.fantasia || empresa.fantasia,
                    razao_social: tenantEmpresa.razao_social || empresa.razao_social,
                    cnpj: tenantEmpresa.cnpj || empresa.cnpj,
                    nome_exibicao: tenantEmpresa.nome_exibicao || empresa.nome_exibicao,
                  }
                : empresa
            )
          : tenantEmpresa
            ? [tenantEmpresa]
            : [];

        console.log("[DEBUG EMPRESA CONTEXT] Lista recebida do servidor:", listaComTenant);

        setEmpresas(listaComTenant);

        if (!listaComTenant.length) {
          console.warn("[DEBUG EMPRESA CONTEXT] Lista vazia!");
          setEmpresaAtual(null);
          localStorage.removeItem("empresa_atual");
          return;
        }

        const empresaSalva = localStorage.getItem("empresa_atual");
        const empresaSalvaObj = empresaSalva ? JSON.parse(empresaSalva) : null;

        if (empresaSalvaObj) {
          console.log("[DEBUG EMPRESA CONTEXT] Tentando restaurar:", empresaSalvaObj);
          const empresaEncontrada = listaComTenant.find(
            (item) =>
              String(item.selector_id ?? item.id) ===
              String(empresaSalvaObj.selector_id ?? empresaSalvaObj.id)
          );

          if (empresaEncontrada) {
            console.log("[DEBUG EMPRESA CONTEXT] Restaurada:", empresaEncontrada);
            setEmpresaAtual(empresaEncontrada);
            return;
          }
        }

        if (listaComTenant.length > 0) {
          const primeiraEmpresa = listaComTenant[0];
          console.log("[DEBUG EMPRESA CONTEXT] Selecionando automática:", primeiraEmpresa);
          setEmpresaAtual(primeiraEmpresa);
          localStorage.setItem("empresa_atual", JSON.stringify(primeiraEmpresa));
        }
      } catch (error) {
        console.error("[DEBUG EMPRESA CONTEXT] Erro:", error);
        setEmpresas([]);
        setEmpresaAtual(null);
        localStorage.removeItem("empresa_atual");
      } finally {
        setLoadingEmpresas(false);
      }
    }

    if (loadingAuth) {
      return;
    }

    if (!isAuthenticated) {
      setEmpresas([]);
      setEmpresaAtual(null);
      localStorage.removeItem("empresa_atual");
      return;
    }

    carregarEmpresas();
  }, [isAuthenticated, loadingAuth]);

  function selecionarEmpresa(empresa) {
    setEmpresaAtual(empresa);
    localStorage.setItem("empresa_atual", JSON.stringify(empresa));
  }

  const value = useMemo(
    () => ({
      empresas,
      empresaAtual,
      selecionarEmpresa,
      loadingEmpresas,
    }),
    [empresas, empresaAtual, loadingEmpresas]
  );

  return (
    <EmpresaContext.Provider value={value}>
      {children}
    </EmpresaContext.Provider>
  );
}

export function useEmpresa() {
  const context = useContext(EmpresaContext);

  if (!context) {
    throw new Error("useEmpresa deve ser usado dentro de EmpresaProvider");
  }

  return context;
}
