import { useEffect } from 'react';
import { Circle, CircleMarker, MapContainer, TileLayer, Tooltip, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import type { CentreSummary } from '../lib/api';
import type { Place } from '../lib/location';
import { useSettings } from '../lib/settings';

// OneMap basemap from SLA: free, Singapore-specific, no billing risk (team decision).
// Attribution with the OneMap logo is required by their terms.
const ONEMAP_ATTRIBUTION =
  '<img src="https://www.onemap.gov.sg/web-assets/images/logo/om_logo.png" style="height:20px;width:20px;display:inline"/>&nbsp;' +
  '<a href="https://www.onemap.gov.sg/" target="_blank" rel="noopener noreferrer">OneMap</a>&nbsp;&copy;&nbsp;contributors&nbsp;&#124;&nbsp;' +
  '<a href="https://www.sla.gov.sg/" target="_blank" rel="noopener noreferrer">Singapore Land Authority</a>';

const COLOR: Record<string, string> = {
  open: '#0f8a76',
  closing_soon: '#d97706',
  closed: '#e11d48',
  not_operating: '#78716c',
};

function FitTo({ centres, place }: { centres: CentreSummary[]; place: Place | null }) {
  const map = useMap();
  useEffect(() => {
    if (place) map.setView([place.lat, place.lng], 14);
    else if (centres.length) map.fitBounds(centres.map((c) => [c.latitude, c.longitude] as [number, number]), { padding: [30, 30], maxZoom: 15 });
  }, [place?.lat, place?.lng, centres.length]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

export default function MapView({
  centres,
  place,
  onSelect,
  selectedId,
  radiusKm,
  className = 'h-[60vh]',
}: {
  centres: CentreSummary[];
  place: Place | null;
  onSelect?: (id: number) => void;
  selectedId?: number | null;
  radiusKm?: number | null;
  className?: string;
}) {
  const { isDark } = useSettings();
  return (
    <MapContainer
      center={[1.3521, 103.8198]}
      zoom={12}
      minZoom={11}
      maxZoom={19}
      maxBounds={[[1.144, 103.535], [1.494, 104.502]]}
      className={`z-0 w-full overflow-hidden rounded-2xl ${className}`}
    >
      <TileLayer
        key={isDark ? 'night' : 'default'}
        url={`https://www.onemap.gov.sg/maps/tiles/${isDark ? 'Night' : 'Default'}/{z}/{x}/{y}.png`}
        attribution={ONEMAP_ATTRIBUTION}
        detectRetina
      />
      {place && (
        <>
          {radiusKm && <Circle center={[place.lat, place.lng]} radius={radiusKm * 1000} pathOptions={{ color: '#0f766e', weight: 1, fillOpacity: 0.05 }} />}
          <CircleMarker center={[place.lat, place.lng]} radius={8} pathOptions={{ color: '#fff', weight: 3, fillColor: '#2563eb', fillOpacity: 1 }}>
            <Tooltip>{place.label}</Tooltip>
          </CircleMarker>
        </>
      )}
      {centres.map((c) => (
        <CircleMarker
          key={c.id}
          center={[c.latitude, c.longitude]}
          radius={c.id === selectedId ? 12 : 8}
          pathOptions={{ color: '#fff', weight: 2, fillColor: COLOR[c.status.state], fillOpacity: 0.95 }}
          eventHandlers={{ click: () => onSelect?.(c.id) }}
        >
          <Tooltip>
            <strong>{c.centre_name}</strong>
            <br />
            {c.status.state === 'closed' ? 'Closed today' : c.status.state === 'closing_soon' ? 'Closing soon' : 'Open today'} · {c.grades.A} grade A stalls
          </Tooltip>
        </CircleMarker>
      ))}
      <FitTo centres={centres} place={place} />
    </MapContainer>
  );
}
