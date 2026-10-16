import { useEffect, useMemo, useState } from 'react';
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from 'react-leaflet';
import { locateCity } from '../utils/geography';
import 'leaflet/dist/leaflet.css';
import '../styles/financial-map.css';

let catalogRequest;
function catalog() {
  if (!catalogRequest) catalogRequest = fetch('/data/municipios.json').then((response) => {
    if (!response.ok) throw new Error('Catálogo de municípios indisponível.');
    return response.json();
  }).catch((error) => { catalogRequest = undefined; throw error; });
  return catalogRequest;
}
function Viewport({ points }) {
  const map = useMap();
  const bounds = useMemo(() => points.map((point) => [point.lat, point.lng]), [points]);
  useEffect(() => {
    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(map.getContainer());
    if (bounds.length) map.fitBounds(bounds, { padding:[36,36], maxZoom:11 });
    return () => observer.disconnect();
  }, [map, bounds]);
  return null;
}

export default function FinancialMap({ cities = [], metricLabel = "Clientes" }) {
  const [municipalities, setMunicipalities] = useState([]);
  const [error, setError] = useState('');
  const [tileError, setTileError] = useState(false);
  useEffect(() => {
    let active = true;
    catalog().then((data) => { if (active) setMunicipalities(data); }).catch((err) => { if (active) setError(err.message); });
    return () => { active = false; };
  }, []);
  const points = useMemo(() => cities.map((city) => locateCity(city, municipalities)).filter(Boolean), [cities, municipalities]);
  const unlocated = municipalities.length ? cities.length - points.length : 0;
  return <section className="financial-real-map" aria-label="Mapa geográfico dos clientes">
    <MapContainer center={[-14.2,-51.9]} zoom={4} scrollWheelZoom={false} className="financial-leaflet-map">
      <TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" maxZoom={19}
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        eventHandlers={{ tileerror:() => setTileError(true), tileload:() => setTileError(false) }} />
      <Viewport points={points} />
      {points.map((point) => <CircleMarker key={point.codigo_ibge} center={[point.lat,point.lng]} radius={Math.min(22,6 + Math.sqrt(Math.max(0,Number(point.quantidade) || 0)) * 2)} pathOptions={{ color:point.cor || '#2563eb', fillOpacity:0.4 }}>
        <Popup><strong>{point.cidade} / {point.uf}</strong><br />{metricLabel}: {point.quantidade}<br /><small>Referência: centro do município. Não representa endereço individual.</small></Popup>
      </CircleMarker>)}
    </MapContainer>
    <div className="financial-map-status" role="status">
      {error ? <p>{error} Os dados por cidade permanecem na tabela.</p> : <p>{points.length} municípios localizados. Pontos indicam o centro do município.</p>}
      {unlocated > 0 && <p>{unlocated} municípios sem localização confirmada. É necessário código IBGE ou nome e UF sem ambiguidade.</p>}
      {tileError && <p>Não foi possível carregar o mapa de ruas. Confira a conexão com o OpenStreetMap; os dados por cidade continuam disponíveis.</p>}
    </div>
  </section>;
}
