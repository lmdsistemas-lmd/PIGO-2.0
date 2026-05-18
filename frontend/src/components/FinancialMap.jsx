import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";

const DEFAULT_CENTER = [-21.5, -42.7];

function getRadius(qtd) {
  if (!qtd) return 6;
  if (qtd < 10) return 8;
  if (qtd < 30) return 12;
  if (qtd < 80) return 16;
  return 22;
}

function FinancialMap({ cities = [] }) {
  return (
    <div style={{ width: "100%", height: "340px", borderRadius: "20px", overflow: "hidden" }}>
      <MapContainer
        center={DEFAULT_CENTER}
        zoom={8}
        scrollWheelZoom={false}
        style={{ width: "100%", height: "100%" }}
      >
        <TileLayer
          attribution="&copy; OpenStreetMap"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {cities.map((cidade, index) => {
          const lat = Number(cidade.lat);
          const lng = Number(cidade.lng);

          if (!lat || !lng) return null;

          return (
            <CircleMarker
              key={index}
              center={[lat, lng]}
              radius={getRadius(cidade.quantidade)}
              pathOptions={{
                color: cidade.cor || "#2563eb",
                fillColor: cidade.cor || "#2563eb",
                fillOpacity: 0.35
              }}
            >
              <Popup>
                <strong>{cidade.cidade}</strong>
                <br />
                Clientes: {cidade.quantidade}
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>
    </div>
  );
}

export default FinancialMap;