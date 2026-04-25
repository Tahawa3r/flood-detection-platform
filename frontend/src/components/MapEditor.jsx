import React, { useRef, useState } from 'react';
import { MapContainer, TileLayer, FeatureGroup, ImageOverlay } from 'react-leaflet';
import { EditControl } from 'react-leaflet-draw';
import L from 'leaflet';

// Use a beautiful dark map tile layer
const STADIA_URL = 'https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png';

export default function MapEditor({ onRegionSelect, predictionResult }) {
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
        zoom={10} 
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer
          url={STADIA_URL}
          attribution='&copy; Stadia Maps'
        />
        <FeatureGroup>
          <EditControl
            position="topright"
            onCreated={onCreated}
            onDeleted={onDeleted}
            draw={{
              polyline: false,
              polygon: true,
              circle: false,
              rectangle: true,
              marker: false,
              circlemarker: false,
            }}
          />
        </FeatureGroup>
        
        {predictionResult && shapeBounds && (
           <ImageOverlay
              url={`${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'}/predictions/${predictionResult.prediction_id}/overlay.png`}
              bounds={shapeBounds}
              opacity={0.85}
              zIndex={10}
           />
        )}
      </MapContainer>
    </div>
  );
}
