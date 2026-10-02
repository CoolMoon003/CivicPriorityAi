import { memo, useEffect, useMemo } from "react";
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Popup,
  useMap,
} from "react-leaflet";
import { damageSeverityLabel, roadDamageLabel } from "../utils/complaintLabels.js";

const VELLORE_CENTER = [12.9165, 79.1325];

const LEVEL_COLOR = {
  CRITICAL: "#ef6d5b",
  HIGH: "#ef6d5b",
  MEDIUM: "#e8b84b",
  LOW: "#6f8db0",
};

function levelColor(level) {
  return LEVEL_COLOR[(level || "").toUpperCase()] || "#6f8db0";
}

function FlyToSelection({ complaint }) {
  const map = useMap();

  useEffect(() => {
    if (
      complaint &&
      complaint.location?.latitude != null &&
      complaint.location?.longitude != null
    ) {
      map.flyTo(
        [complaint.location.latitude, complaint.location.longitude],
        Math.max(map.getZoom(), 15),
        { duration: 0.6 }
      );
    }
  // Complaint objects are recreated by the dashboard's background refresh.
  // Depend on selection/location primitives so polling cannot interrupt map gestures.
  // eslint-disable-next-line react-hooks/exhaustive-deps -- polling recreates complaint objects; primitive deps avoid interrupting map gestures.
  }, [complaint?.id, complaint?.location?.latitude, complaint?.location?.longitude, map]);

  return null;
}

function MapPanelView({ complaints, selectedId, onSelect }) {
  const markersWithCoords = useMemo(() => complaints.filter(
    (c) => c.location?.latitude != null && c.location?.longitude != null
  ), [complaints]);

  const selectedComplaint = markersWithCoords.find(
    (c) => c.id === selectedId
  );

  return (
    <div className="map-panel">
      <div className="map-panel-header">
        <div>
          <h2>Vellore Road Network</h2>
          <p>Complaint locations · overall priority overlay</p>
        </div>
        <span className="demo-tag">Demo data</span>
      </div>

      <div className="map-frame">
        <MapContainer
          center={VELLORE_CENTER}
          zoom={13}
          scrollWheelZoom
          preferCanvas
          className="leaflet-container-custom"
        >
          <TileLayer
            attribution='&copy; OpenStreetMap contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          <FlyToSelection complaint={selectedComplaint} />

          {markersWithCoords.map((complaint) => {
            const level = complaint.priority?.level;
            const isSelected = complaint.id === selectedId;
            return (
              <CircleMarker
                key={complaint.id}
                center={[
                  complaint.location.latitude,
                  complaint.location.longitude,
                ]}
                radius={isSelected ? 10 : 7}
                pathOptions={{
                  color: levelColor(level),
                  fillColor: levelColor(level),
                  fillOpacity: isSelected ? 0.9 : 0.65,
                  weight: isSelected ? 3 : 1.5,
                }}
                eventHandlers={{
                  click: () => onSelect(complaint.id),
                }}
              >
                <Popup>
                  <div className="map-popup">
                    <strong>
                      Complaint #{complaint.id} &middot;{" "}
                      {complaint.road?.name || "Unknown road"}
                    </strong>
                    <div className="map-popup-row">
                      <span>Overall priority score</span>
                      <span>{complaint.priority?.score ?? "—"}</span>
                    </div>
                    <div className="map-popup-row">
                      <span>Overall priority level</span>
                      <span>{complaint.priority?.level || "—"}</span>
                    </div>
                    <div className="map-popup-row">
                      <span>Road damage</span>
                      <span>{roadDamageLabel(complaint.damage)}</span>
                    </div>
                    <div className="map-popup-row">
                      <span>Damage severity</span>
                      <span>{damageSeverityLabel(complaint.damage)}</span>
                    </div>
                    <div className="map-popup-row">
                      <span>Status</span>
                      <span>{complaint.status || "—"}</span>
                    </div>
                    <div className="map-popup-note">
                      Development submission — not a verified public
                      complaint.
                    </div>
                  </div>
                </Popup>
              </CircleMarker>
            );
          })}
        </MapContainer>

        <div className="map-legend">
          <div className="legend-row">
            <span className="legend-dot" style={{ background: LEVEL_COLOR.HIGH }} />
            High / critical priority
          </div>
          <div className="legend-row">
            <span className="legend-dot" style={{ background: LEVEL_COLOR.MEDIUM }} />
            Medium priority
          </div>
          <div className="legend-row">
            <span className="legend-dot" style={{ background: LEVEL_COLOR.LOW }} />
            Low priority
          </div>
          <div className="legend-row legend-demo">Demo data</div>
        </div>
      </div>
    </div>
  );
}

export const MapPanel = memo(MapPanelView);
