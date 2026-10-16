import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [form, setForm] = useState({
    cnpj: "",
    login: "",
    senha: "",
  });

  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();

    try {
      setLoading(true);
      setErro("");

      await login(form.cnpj, form.login, form.senha);


      navigate("/dashboard/vendas", { replace: true });
    } catch (error) {
      setErro(error.message || "Não foi possível realizar o login.");
    } finally {
      setLoading(false);
    }
  }

  function handleChange(event) {
    const { name, value } = event.target;

    setForm((current) => ({
      ...current,
      [name]: value,
    }));
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background:
          "linear-gradient(135deg, #0f172a 0%, #1e293b 45%, #334155 100%)",
        padding: "24px",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "420px",
          background: "#ffffff",
          borderRadius: "20px",
          padding: "32px",
          boxShadow: "0 20px 60px rgba(0,0,0,0.25)",
        }}
      >
        <div style={{ marginBottom: "24px", textAlign: "center" }}>
          <div
            style={{
              fontSize: "14px",
              color: "#64748b",
              marginBottom: "8px",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
          >
            ERP Modernizado
          </div>

          <h1
            style={{
              margin: 0,
              fontSize: "28px",
              color: "#0f172a",
            }}
          >
            Acessar Dashboard
          </h1>

          <p
            style={{
              marginTop: "10px",
              color: "#475569",
              fontSize: "15px",
            }}
          >
            Entre com seu usuário do ERP para acessar a demonstração.
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: "16px" }}>
            <label
              htmlFor="cnpj"
              style={{
                display: "block",
                marginBottom: "8px",
                fontWeight: 600,
                color: "#1e293b",
              }}
            >
              CNPJ
            </label>

            <input
              id="cnpj"
              name="cnpj"
              type="text"
              value={form.cnpj}
              onChange={handleChange}
              placeholder="Digite o CNPJ da empresa"
              required
              style={{
                width: "100%",
                height: "46px",
                borderRadius: "12px",
                border: "1px solid #cbd5e1",
                padding: "0 14px",
                fontSize: "15px",
                outline: "none",
                boxSizing: "border-box",
              }}
            />
          </div>

          <div style={{ marginBottom: "16px" }}>
            <label
              htmlFor="login"
              style={{
                display: "block",
                marginBottom: "8px",
                fontWeight: 600,
                color: "#1e293b",
              }}
            >
              Usuário
            </label>

            <input
              id="login"
              name="login"
              type="text"
              value={form.login}
              onChange={handleChange}
              placeholder="Digite seu usuário"
              autoComplete="username"
              required
              style={{
                width: "100%",
                height: "46px",
                borderRadius: "12px",
                border: "1px solid #cbd5e1",
                padding: "0 14px",
                fontSize: "15px",
                outline: "none",
                boxSizing: "border-box",
              }}
            />
          </div>

          <div style={{ marginBottom: "18px" }}>
            <label
              htmlFor="senha"
              style={{
                display: "block",
                marginBottom: "8px",
                fontWeight: 600,
                color: "#1e293b",
              }}
            >
              Senha
            </label>

            <input
              id="senha"
              name="senha"
              type="password"
              value={form.senha}
              onChange={handleChange}
              placeholder="Digite sua senha"
              autoComplete="current-password"
              required
              style={{
                width: "100%",
                height: "46px",
                borderRadius: "12px",
                border: "1px solid #cbd5e1",
                padding: "0 14px",
                fontSize: "15px",
                outline: "none",
                boxSizing: "border-box",
              }}
            />
          </div>

          {erro ? (
            <div
              style={{
                marginBottom: "16px",
                padding: "12px 14px",
                borderRadius: "12px",
                background: "#fef2f2",
                color: "#b91c1c",
                fontSize: "14px",
              }}
            >
              {erro}
            </div>
          ) : null}

          <button
            type="submit"
            disabled={loading}
            style={{
              width: "100%",
              height: "48px",
              border: "none",
              borderRadius: "12px",
              background: loading ? "#94a3b8" : "#2563eb",
              color: "#ffffff",
              fontSize: "16px",
              fontWeight: 700,
              cursor: loading ? "not-allowed" : "pointer",
            }}
          >
            {loading ? "Entrando..." : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}