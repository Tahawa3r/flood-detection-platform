import React, { useState } from 'react';
import MapEditor from './components/MapEditor';
import ControlPanel from './components/ControlPanel';

function App() {
  // Region GeoJSON selected by user on the map
  const [regionGeoJson, setRegionGeoJson] = useState(null);
  
  // Results from AI Inference
  const [predictionResult, setPredictionResult] = useState(null);

  return (
    <div className="app-container">
      <ControlPanel 
        regionGeoJson={regionGeoJson} 
        onPredictionComplete={setPredictionResult}
        onRegionSelect={setRegionGeoJson}
      />
      <MapEditor 
        onRegionSelect={setRegionGeoJson}
        regionGeoJson={regionGeoJson}
        predictionResult={predictionResult}
      />
    </div>
  );
}

export default App;
