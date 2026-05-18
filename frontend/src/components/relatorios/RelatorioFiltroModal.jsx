import "../../styles/relatorios.css";

export default function RelatorioPreviewTable({
  colunas = [],
  linhas = [],
  totalRegistros = 0,
}) {
  if (!colunas.length) {
    return <div className="preview-empty">Nenhum dado para exibir.</div>;
  }

  return (
    <div className="preview-table-wrap">
      <table className="preview-table">
        <thead>
          <tr>
            {colunas.map((coluna) => (
              <th key={coluna}>{coluna}</th>
            ))}
          </tr>
        </thead>

        <tbody>
          {linhas.map((linha, index) => (
            <tr key={index}>
              {colunas.map((coluna) => (
                <td key={coluna}>
                  {linha[coluna] !== null && linha[coluna] !== undefined
                    ? String(linha[coluna])
                    : ""}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}