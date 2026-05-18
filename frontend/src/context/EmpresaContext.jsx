import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { listarEmpresas } from "../services/empresaService";
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

        const data = await listarEmpresas();
        const lista = Array.isArray(data) ? data : [];

        console.log("[DEBUG EMPRESA CONTEXT] Lista recebida do servidor:", lista);

        setEmpresas(lista);

        if (!lista.length) {
          console.warn("[DEBUG EMPRESA CONTEXT] Lista vazia!");
          setEmpresaAtual(null);
          localStorage.removeItem("empresa_atual");
          return;
        }

        const empresaSalva = localStorage.getItem("empresa_atual");
        const empresaSalvaObj = empresaSalva ? JSON.parse(empresaSalva) : null;

        if (empresaSalvaObj) {
          console.log("[DEBUG EMPRESA CONTEXT] Tentando restaurar:", empresaSalvaObj);
          const empresaEncontrada = lista.find(
            (item) => String(item.id) === String(empresaSalvaObj.id)
          );

          if (empresaEncontrada) {
            console.log("[DEBUG EMPRESA CONTEXT] Restaurada:", empresaEncontrada);
            setEmpresaAtual(empresaEncontrada);
            return;
          }
        }

        if (lista.length > 0) {
          const primeiraEmpresa = lista[0];
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