import React, { useState } from 'react';
import { MapPin, Brain, Activity, CheckCircle, AlertCircle } from 'lucide-react';

export default function ControlPanel({ regionGeoJson, onPredictionComplete }) {
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const handlePredict = async () => {
    if (!regionGeoJson) {
      setError('Please select a region on the map first');
      return;
    }

    setIsProcessing(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'}/predictions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          region_geojson: regionGeoJson.geojson,
          threshold: 0.5
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setResult(data);
      onPredictionComplete(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="control-panel">
      <div className="panel-header">
        <h2><Brain className="icon" /> Flood Detection</h2>
      </div>
      
      <div className="panel-content">
        <div className="status-section">
          <div className="status-item">
            <MapPin className="icon" />
            <span>Region: {regionGeoJson ? 'Selected' : 'Not selected'}</span>
          </div>
          
          {isProcessing && (
            <div className="status-item processing">
              <Activity className="icon spin" />
              <span>Processing prediction...</span>
            </div>
          )}
          
          {result && (
            <div className="status-item success">
              <CheckCircle className="icon" />
              <span>Prediction complete</span>
            </div>
          )}
          
          {error && (
            <div className="status-item error">
              <AlertCircle className="icon" />
              <span>Error: {error}</span>
            </div>
          )}
        </div>

        <button 
          className="predict-button"
          onClick={handlePredict}
          disabled={!regionGeoJson || isProcessing}
        >
          {isProcessing ? 'Processing...' : 'Run Prediction'}
        </button>
      </div>
    </div>
  );
}
