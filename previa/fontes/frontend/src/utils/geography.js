export function normalizedCity(value) {
  return String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim().toLocaleUpperCase('pt-BR');
}

export function locateCity(city, municipalities) {
  const code = String(city.codigo_ibge || '').trim();
  const matches = code ? municipalities.filter((item) => item.ibge === code) : municipalities.filter((item) => normalizedCity(item.nome) === normalizedCity(city.cidade) && (!city.uf || item.uf === normalizedCity(city.uf)));
  // Homonymous municipalities must never be located by an arbitrary first match.
  if (matches.length !== 1) return null;
  const point = matches[0];
  if (!Number.isFinite(point.lat) || !Number.isFinite(point.lng) || Math.abs(point.lat) > 90 || Math.abs(point.lng) > 180) return null;
  return { ...city, lat:point.lat, lng:point.lng, uf:point.uf, codigo_ibge:point.ibge };
}
