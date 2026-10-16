import { useState } from "react";
import { interpretReportPrompt } from "../../services/reportsService";
import { ASSISTANT_EXAMPLES, BUSINESS_LABELS, CATEGORY_BY_KEY, CHARTS, PERIOD_LABELS } from "./reportConfig";

export default function ReportAssistantPanel({ companyId, onApply, compact = false, onClose }) {
  const [prompt, setPrompt] = useState("");
  const [result, setResult] = useState(null);
  const [answers, setAnswers] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function interpret(nextAnswers = answers) {
    if (!companyId) return setError("Selecione uma empresa ERP para usar o assistente.");
    setLoading(true); setError("");
    try { setResult(await interpretReportPrompt({ prompt, company_id: Number(companyId), answers: nextAnswers })); setAnswers(nextAnswers); }
    catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }

  return <aside className={`reports-assistant-panel ${compact ? "compact" : ""}`} aria-label="Assistente de relatórios">
    <header><div><span>Assistente</span><h2>Crie com linguagem de negócio</h2></div>{onClose && <button onClick={onClose} aria-label="Fechar assistente">×</button>}</header>
    <p>Descreva o relatório desejado. Nada será executado automaticamente.</p>
    <textarea maxLength="1000" value={prompt} onChange={(event) => { setPrompt(event.target.value); setResult(null); }} placeholder="Quero o faturamento por vendedor deste mês" />
    <button className="reports-button primary" disabled={loading || prompt.trim().length < 3} onClick={() => interpret()}>{loading ? "Interpretando…" : "Interpretar"}</button>
    <div className="assistant-examples">{ASSISTANT_EXAMPLES.map((example) => <button key={example} onClick={() => { setPrompt(example); setResult(null); }}>{example}</button>)}</div>
    {error && <div className="reports-inline-error">{error}</div>}
    {result && !result.success && <div className="assistant-result warning"><strong>{result.message || "Preciso confirmar um detalhe."}</strong>{result.questions?.map((question) => <div key={question.id}><p>{question.question}</p>{question.options.map((option) => <button key={option.value} onClick={() => { const next = { ...answers, [question.id]: option.value }; interpret(next); }}>{option.label}</button>)}</div>)}{!!result.unavailable_concepts?.length && <p>Indisponível: {result.unavailable_concepts.join(", ")}</p>}</div>}
    {result?.success && <div className="assistant-result"><span>Entendimento</span><dl><div><dt>Categoria</dt><dd>{CATEGORY_BY_KEY[result.report_definition.category]?.label}</dd></div><div><dt>Métrica</dt><dd>{result.intent.metrics.map((item) => BUSINESS_LABELS[item] || item).join(", ")}</dd></div><div><dt>Dimensão</dt><dd>{result.intent.dimensions.map((item) => BUSINESS_LABELS[item] || item).join(", ") || "Sem agrupamento"}</dd></div><div><dt>Período</dt><dd>{PERIOD_LABELS[result.intent.period?.type] || "Não informado"}</dd></div><div><dt>Visualização</dt><dd>{CHARTS[result.report_definition.chart]}</dd></div></dl><button className="reports-button primary" onClick={() => onApply(result.report_definition, prompt)}>Abrir no Builder</button></div>}
  </aside>;
}
