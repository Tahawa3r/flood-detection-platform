import React, { useRef, useState } from 'react';
import { MapContainer, TileLayer, FeatureGroup, ImageOverlay, GeoJSON, useMap } from 'react-leaflet';
import { EditControl } from 'react-leaflet-draw';
import L from 'leaflet';

// Use a light, Google Maps-style tile layer
const MAPTILER_URL = `https://api.maptiler.com/maps/streets-v2/{z}/{x}/{y}{r}.png?key=${import.meta.env.VITE_MAPTILER_API_KEY || 'dzAvc3HYPwk9k2fvjrRt'}`;

// Debug: Log API key to console
console.log('MapTiler API Key:', import.meta.env.VITE_MAPTILER_API_KEY ? 'Set' : 'Missing');

function MapViewUpdater({ region }) {
  const map = useMap();
  React.useEffect(() => {
    if (region && region.geojson) {
      const layer = L.geoJSON(region.geojson);
      const bounds = layer.getBounds();
      map.fitBounds(bounds, { padding: [50, 50] });
    }
  }, [region, map]);
  return null;
}

export default function MapEditor({ onRegionSelect, regionGeoJson, predictionResult }) {
  const [shapeBounds, setShapeBounds] = useState(null);

  const onCreated = (e) => {
    const { layerType, layer } = e;
    if (layerType === 'rectangle' || layerType === 'polygon') {
      const geo = layer.toGeoJSON();
      const bounds = layer.getBounds();
      
      onRegionSelect({ geojson: geo.geometry });
      
      // Store the bounds so we perfectly align the Deep Learning output on top of it later!
      setShapeBounds([
        [bounds.getSouth(), bounds.getWest()],
        [bounds.getNorth(), bounds.getEast()]
      ]);
    }
  };

  const onDeleted = () => {
    onRegionSelect(null);
    setShapeBounds(null);
  };

  return (
    <div className="map-workspace">
        <MapContainer
          center={[35.7595, -5.8340]}
          zoom={13}
          style={{ height: '100%', width: '100%' }}
        >
          <TileLayer
            url={`https://api.maptiler.com/maps/satellite/{z}/{x}/{y}.jpg?key=${import.meta.env.VITE_MAPTILER_API_KEY || 'dzAvc3HYPwk9k2fvjrRt'}`}
            attribution='&copy; <a href="https://www.maptiler.com/copyright/">MapTiler</a> contributors'
          />
          
          <FeatureGroup>
            <EditControl
              position="topright"
              onCreated={onCreated}
              onDeleted={onDeleted}
              draw={{
                polyline: false,
                polygon: {
                  showArea: false,
                  showLength: false,
                },
                circle: false,
                rectangle: {
                  showArea: false,
                },
                marker: false,
                circlemarker: false,
              }}
            />
        </FeatureGroup>

        {regionGeoJson && regionGeoJson.geojson && (
          <GeoJSON 
            data={regionGeoJson.geojson} 
            style={{ color: '#00d2ff', weight: 2, fillOpacity: 0.1 }} 
          />
        )}

        <MapViewUpdater region={regionGeoJson} />

        {predictionResult && shapeBounds && (
            <ImageOverlay
              url={`${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8080'}/predictions/${predictionResult.prediction_id}/overlay.png`}
              bounds={shapeBounds}
              opacity={0.7}
              zIndex={1000}
            />
          )}

          {/* Map Legend */}
          <div className="map-legend">
            <h4>Map Legend</h4>
            <div className="legend-item">
              <span className="legend-color" style={{ backgroundColor: 'rgba(59, 130, 246, 0.4)', border: '2px solid #3b82f6' }}></span>
              <span>Selected Region</span>
            </div>
            <div className="legend-item">
              <span className="legend-color" style={{ backgroundColor: 'rgba(0, 0, 255, 0.8)' }}></span>
              <span>Detected Flood</span>
            </div>
          </div>
        </MapContainer>
    </div>
  );
}
