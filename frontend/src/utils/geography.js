export function normalizedCity(value) {
  return String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim().toLocaleUpperCase('pt-BR');
}

export function locateCity(city, municipalities) {
  const code = String(city.codigo_ibge || city.ibgeCode || '').trim();
  const state = city.uf || city.state;
  const name = city.cidade || city.city;
  const source = city.resolutionSource;
  const latitude = city.latitude == null ? NaN : Number(city.latitude);
  const longitude = city.longitude == null ? NaN : Number(city.longitude);
  if (['IBGE_CODE', 'CITY_STATE', 'MANUAL_OVERRIDE'].includes(source)
      && Number.isFinite(latitude) && Number.isFinite(longitude)
      && Math.abs(latitude) <= 90 && Math.abs(longitude) <= 180) {
    return { ...city, cidade:name, quantidade:city.quantidade ?? city.customers,
      lat:latitude, lng:longitude, uf:state || '—',
      codigo_ibge:code || `${name}/${state || ''}/${latitude}/${longitude}` };
  }
  const matches = code ? municipalities.filter((item) => item.ibge === code) : municipalities.filter((item) => normalizedCity(item.nome) === normalizedCity(name) && (!state || item.uf === normalizedCity(state)));
  // Homonymous municipalities must never be located by an arbitrary first match.
  if (matches.length !== 1) return null;
  const point = matches[0];
  if (!Number.isFinite(point.lat) || !Number.isFinite(point.lng) || Math.abs(point.lat) > 90 || Math.abs(point.lng) > 180) return null;
  return { ...city, lat:point.lat, lng:point.lng, uf:point.uf, codigo_ibge:point.ibge };
}
