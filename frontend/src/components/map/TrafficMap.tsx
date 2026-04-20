import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  MapContainer,
  TileLayer,
  Polyline,
  CircleMarker,
  Tooltip,
  useMap,
  Popup,
  Pane
} from 'react-leaflet';

import 'leaflet/dist/leaflet.css';
import { api } from '../../services/api';
import { 
  useFeedStore, 
  useIncidentStore, 
  useUIStore, 
  deriveAlertPriority 
} from '../../store';
import { CameraPopup } from './CameraPopup';
import { ActionButton } from '../UIKit';

const DEFAULT_ZOOM = 14;

const CAMERA_POINTS = [
  { id: '1', name: 'W 34th St & 7th Ave', lat: 40.7505, lng: -73.9904 },
  { id: '2', name: 'Broadway & 34th St', lat: 40.7484, lng: -73.9878 },
  { id: '3', name: '10th Ave & 42nd St', lat: 40.7579, lng: -73.998 },
  { id: '4', name: 'Tribune Chowk', lat: 30.727, lng: 76.7675 },
  { id: '5', name: 'Piccadily Chowk', lat: 30.7246, lng: 76.7621 },
];

type LatLng = [number, number];

const toLatLng = (coords: number[][] = []): LatLng[] =>
  coords.filter((c) => c.length >= 2).map((c) => [c[1], c[0]]);





const MapController: React.FC<{
  center: { lat: number; lng: number; zoom?: number } | null;
  focusIncident?: { id: string; location: { lat: number; lng: number } } | null;
}> = ({ center, focusIncident }) => {
  const map = useMap();
  const lastFocusedIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!center || focusIncident?.id) return;
    map.flyTo([center.lat, center.lng], center.zoom || DEFAULT_ZOOM, { duration: 1.2 });
  }, [center, focusIncident?.id, map]);

  useEffect(() => {
    if (!focusIncident?.id) return;
    if (lastFocusedIdRef.current === focusIncident.id) return;
    lastFocusedIdRef.current = focusIncident.id;
    map.flyTo([focusIncident.location.lat, focusIncident.location.lng], 16, { duration: 1.0 });
  }, [focusIncident?.id, focusIncident?.location?.lat, focusIncident?.location?.lng, map]);

  return null;
};

const TrafficMap: React.FC = () => {
  const { cityCenter, city } = useFeedStore();
  const { 
    incidents, 
    currentIncident, 
    setCollisions, 
    setIncident, 
    setLLMOutput, 
    incidentRoutes, 
    congestionZones,
    updateIncidentPoliceDispatch
  } = useIncidentStore();
  const { focusMode, pushFocusStack, activeFocusId, addUndoAction } = useUIStore();
  
  const [selectedCamera, setSelectedCamera] = useState<(typeof CAMERA_POINTS)[number] | null>(null);
  
  const focusedIncident = useMemo(() => {
    if (activeFocusId) return incidents.find(i => i.id === activeFocusId && i.city === city) || null;
    return currentIncident && currentIncident.city === city ? currentIncident : null;
  }, [activeFocusId, currentIncident, incidents, city]);

  useEffect(() => {
    if (!currentIncident) return;
    api.getNearbyCollisions(currentIncident.location.lat, currentIncident.location.lng, 0.01)
      .then((data) => {
        if (Array.isArray(data)) setCollisions(data);
      })
      .catch(() => {});
  }, [currentIncident?.id, setCollisions]);

  const activeIncidents = useMemo(
    () => incidents.filter((inc) => inc.status === 'active' && inc.city === city),
    [incidents, city],
  );

  const routePairs = useMemo(() => {
    return incidentRoutes.filter((rp: any) => {
      if ((rp as any).is_consolidated && (rp as any).incident_ids) {
        return (rp as any).incident_ids.some((id: string) =>
          activeIncidents.some((inc) => inc.id === id),
        );
      }
      return activeIncidents.some((inc) => inc.id === rp.incidentId);
    });
  }, [incidentRoutes, activeIncidents]);

  const cityCongestionZones = useMemo(
    () => congestionZones.filter((z: any) => (z.city || z._city || '').toLowerCase() === city),
    [congestionZones, city],
  );

  const mapCenter: LatLng = cityCenter ? [cityCenter.lat, cityCenter.lng] : [40.7128, -74.006];

  const handleMapAction = (type: 'diversion' | 'dispatch', inc: any) => {
    if (type === 'dispatch') {
      api.dispatchPolice(inc.id, 'Operator').then(() => {
         updateIncidentPoliceDispatch(inc.id, {
            police_dispatched: true,
            police_dispatched_at: new Date().toISOString()
         });
         addUndoAction({
            id: `map-dispatch-${inc.id}`,
            label: `Dispatch confirmed for ${inc.on_street}`,
            onUndo: () => updateIncidentPoliceDispatch(inc.id, { police_dispatched: false }),
            onCommit: () => {}
         });
      });
    }
  };

  return (
    <div className="w-full h-full relative group">
      <MapContainer
        center={mapCenter}
        zoom={cityCenter?.zoom || DEFAULT_ZOOM}
        className="w-full h-full bg-bg"
        zoomControl={false}
      >
        <MapController center={cityCenter} focusIncident={focusedIncident} />
        
        {/* CARTO DB DARK MATTER */}
        <TileLayer
          attribution='&copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />

        <Pane name="congestion" style={{ zIndex: 200 }}>
          {cityCongestionZones
            .flatMap((z: any) => z.segment_geometries || [])
            .filter((seg: any) => Array.isArray(seg.geometry) && seg.geometry.length >= 2)
            .map((seg: any, i: number) => (
              <Polyline
                key={`congestion-seg-${seg.segment_id || i}`}
                positions={toLatLng(seg.geometry)}
                pathOptions={{
                  color: 'var(--color-warning)',
                  weight: 8,
                  opacity: focusMode === 'incident' ? 0.3 : 0.5,
                }}
              />
            ))}
        </Pane>

        <Pane name="routes" style={{ zIndex: 400 }}>
          {routePairs.map((rp: any, i: number) => {
            const blocked = toLatLng(rp.blocked?.geometry?.coordinates || []);
            const alternate = toLatLng(rp.alternate?.geometry?.coordinates || []);
            const isRelevant = !focusedIncident || rp.incidentId === focusedIncident.id;
            
            return (
              <React.Fragment key={`route-${rp.incidentId || i}`}>
                {alternate.length >= 2 && (
                  <Polyline 
                    positions={alternate} 
                    pathOptions={{ 
                        color: 'var(--color-success)', 
                        weight: 6, 
                        opacity: isRelevant ? 0.9 : 0.2,
                        dashArray: '10, 10'
                    }} 
                  />
                )}
                {blocked.length >= 2 && (
                  <Polyline 
                    positions={blocked} 
                    pathOptions={{ 
                        color: 'var(--color-critical)', 
                        weight: 8, 
                        opacity: isRelevant ? 1 : 0.2,
                        dashArray: '8, 8'
                    }} 
                  />
                )}
              </React.Fragment>
            );
          })}
        </Pane>

        <Pane name="incidents" style={{ zIndex: 600 }}>
          {activeIncidents.map((inc) => {
            const priority = deriveAlertPriority(inc);
            const isFocused = activeFocusId === inc.id;
            const pos: LatLng = [inc.location.lat, inc.location.lng];
            
            return (
              <React.Fragment key={`inc-${inc.id}`}>
                <CircleMarker
                  center={pos}
                  radius={isFocused ? 12 : 8}
                  pathOptions={{
                    fillColor: priority === 'P0' || priority === 'P1' ? 'var(--color-critical)' : 'var(--color-warning)',
                    fillOpacity: focusMode === 'incident' && !isFocused ? 0.3 : 0.9,
                    color: isFocused ? 'white' : 'transparent',
                    weight: 2
                  }}
                  eventHandlers={{
                    click: () => {
                        setIncident(inc);
                        pushFocusStack(inc.id);
                        api.getLLMOutput(inc.id).then(setLLMOutput).catch(() => {});
                    },
                  }}
                >
                  <Tooltip direction="top" permanent={isFocused}>
                    <span className="font-mono text-[10px] font-bold uppercase tracking-tight">
                      {inc.on_street}
                    </span>
                  </Tooltip>
                  
                  <Popup className="custom-scada-popup">
                    <div className="p-2 min-w-[200px]">
                        <div className="flex justify-between items-center mb-3">
                            <span className="badge bg-critical text-bg">CRITICAL</span>
                            <span className="text-[9px] font-mono text-text-dim">#{inc.id.slice(0,6)}</span>
                        </div>
                        <h4 className="text-sm font-bold text-text-bright mb-4 uppercase">{inc.on_street}</h4>
                        <div className="space-y-2">
                             <ActionButton 
                                label="View Details" 
                                onClick={() => pushFocusStack(inc.id)} 
                                className="w-full"
                             />
                             <ActionButton 
                                label="Auto Diversion" 
                                intent="caution"
                                onClick={() => handleMapAction('diversion', inc)}
                                className="w-full"
                             />
                             <ActionButton 
                                label="Dispatch Police" 
                                intent="danger"
                                onClick={() => handleMapAction('dispatch', inc)}
                                className="w-full"
                             />
                        </div>
                    </div>
                  </Popup>
                </CircleMarker>
                
                {(priority === 'P0' || priority === 'P1') && (
                    <div style={{ pointerEvents: 'none' }}>
                         {/* Pulse effect via custom icon overlay logic is tricky in leaflet-react, 
                             so we just use the static circles for now but the CircleMarker has the colors */}
                    </div>
                )}
              </React.Fragment>
            );
          })}
        </Pane>

        <Pane name="cameras" style={{ zIndex: 300 }}>
          {CAMERA_POINTS.map((cam) => (
            <CircleMarker
              key={`cam-${cam.id}`}
              center={[cam.lat, cam.lng]}
              radius={5}
              pathOptions={{ 
                  color: 'var(--color-info)', 
                  weight: 1, 
                  fillColor: 'var(--color-info)', 
                  fillOpacity: 0.7,
                  opacity: focusMode === 'incident' ? 0.2 : 0.6
              }}
              eventHandlers={{
                click: () => setSelectedCamera(cam),
              }}
            />
          ))}
        </Pane>
        
        {selectedCamera && (
            <CameraPopup cam={selectedCamera} onClose={() => setSelectedCamera(null)} />
        )}

      </MapContainer>
      
      {/* MAP CONTROLS OVERLAY */}
      <div className="absolute top-4 right-4 z-[1000] flex flex-col gap-2">
           <div className="bg-bg/80 border border-border-dim p-1 rounded-sm flex flex-col">
                <button className="p-2 text-text-dim hover:text-text-bright transition-colors">+</button>
                <div className="h-[1px] bg-border-dim mx-1" />
                <button className="p-2 text-text-dim hover:text-text-bright transition-colors">-</button>
           </div>
      </div>
    </div>
  );
};

export default TrafficMap;
