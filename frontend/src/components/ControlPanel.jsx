import React, { useState, useEffect } from 'react';
import { 
  MapPin, 
  Brain, 
  Activity, 
  CheckCircle, 
  AlertCircle, 
  Layers, 
  Sparkles, 
  MapPinOff, 
  Waves, 
  Shield, 
  Download, 
  Info, 
  Play, 
  Loader2,
  Calendar,
  ChevronRight
} from 'lucide-react';

export default function ControlPanel({ regionGeoJson, onPredictionComplete, onRegionSelect }) {
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState(null);
  const [riskAssessment, setRiskAssessment] = useState(null);
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [userLocation, setUserLocation] = useState(null);
  const [customRegions, setCustomRegions] = useState([]);
  const [locationError, setLocationError] = useState(null);
  
  // Date states for intervals
  const [startPre, setStartPre] = useState("2024-01-01");
  const [endPre, setEndPre] = useState("2024-01-15");
  const [startPost, setStartPost] = useState("2024-01-20");
  const [endPost, setEndPost] = useState("2024-02-05");

  useEffect(() => {
    // Location Detection
    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => setUserLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
        (err) => setLocationError(`Location denied: ${err.message}`)
      );
    }

    // Fetch Models
    const fetchModels = async () => {
      try {
        const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8080'}/models/`);
        const data = await response.json();
        setModels(data);
        if (data.length > 0) setSelectedModel(data[0].id);
      } catch (err) {
        setError('Connection to AI backend failed.');
      }
    };

    // Fetch Regions
    const fetchRegions = async () => {
      try {
        const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8080'}/regions/`);
        const data = await response.json();
        setCustomRegions(data);
      } catch (err) {
        console.error('Failed to fetch regions:', err);
      }
    };

    fetchModels();
    fetchRegions();
  }, []);

  const handlePredict = async () => {
    if (!regionGeoJson) {
      setError('Please define a region on the map.');
      return;
    }

    setIsProcessing(true);
    setError(null);
    setRiskAssessment(null);

    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8080';
      let regionData = regionGeoJson;
      
      // 1. Register Region if it doesn't have an ID
      if (!regionGeoJson.id) {
        const regionRes = await fetch(`${apiUrl}/regions/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: `Analysis_${Date.now()}`,
            geojson: regionGeoJson.geojson
          })
        });
        if (!regionRes.ok) throw new Error("Failed to register region");
        regionData = await regionRes.json();
      }

      // 2. Build Dataset
      const datasetRes = await fetch(`${apiUrl}/datasets/build`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          region_id: regionData.id,
          start_pre: startPre,
          end_pre: endPre,
          start_post: startPost,
          end_post: endPost,
          scale: 100.0,
          patch_size: 256.0
        })
      });
      if (!datasetRes.ok) throw new Error("Failed to build dataset");
      const datasetData = await datasetRes.json();

      // 3. Start Prediction
      const predictRes = await fetch(`${apiUrl}/predictions/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model_id: selectedModel,
          region_id: regionData.id,
          dataset_id: datasetData.dataset_id,
          start_pre: startPre,
          end_pre: endPre,
          start_post: startPost,
          end_post: endPost
        })
      });
      if (!predictRes.ok) throw new Error(`Prediction failed: ${predictRes.statusText}`);
      const predictData = await predictRes.json();
      
      onPredictionComplete(predictData);
      pollForResults(predictData.prediction_id);
    } catch (err) {
      setError(err.message);
      setIsProcessing(false);
    }
  };

  const pollForResults = async (predictionId) => {
    let attempts = 0;
    const maxAttempts = 100; // Large enough for slow GEE exports
    
    const poll = async () => {
      try {
        const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8080'}/predictions/${predictionId}/results`);
        if (!res.ok) throw new Error("Status check failed");
        
        const data = await res.json();
        
        // Terminal states
        if (['completed', 'fallback_completed', 'upgraded'].includes(data.status)) {
           if (data.risk_assessment) {
             setRiskAssessment(data.risk_assessment);
             setIsProcessing(false);
             return;
           }
        }
        
        if (data.status === 'failed' || data.status === 'error') {
          setError('Analysis failed: ' + (data.message || 'Unknown error'));
          setIsProcessing(false);
          return;
        }

        // Continue polling if not in terminal state or if metadata is still being written
        attempts++;
        if (attempts < maxAttempts) {
          setTimeout(poll, 3000);
        } else {
          setError('Analysis timed out.');
          setIsProcessing(false);
        }
      } catch (err) {
        console.error("Polling error:", err);
        // Retry anyway for transient network issues
        attempts++;
        if (attempts < maxAttempts) {
          setTimeout(poll, 5000);
        } else {
          setError('Connection lost.');
          setIsProcessing(false);
        }
      }
    };
    poll();
  };

  return (
    <aside className="control-panel">
      <div className="panel-header">
        <h2><Waves size={28} /> Sentinel-AI</h2>
      </div>

      <div className="panel-content">
        {/* Status Hub */}
        <div className="status-section">
          <div className={`status-item ${userLocation ? 'success' : 'error'}`}>
            {userLocation ? <MapPin className="icon" /> : <MapPinOff className="icon" />}
            <span>{userLocation ? 'Satellite Signal: Strong' : locationError || 'Signal Lost'}</span>
          </div>

          <div className={`status-item ${regionGeoJson ? 'success' : 'processing'}`}>
            {regionGeoJson ? <CheckCircle className="icon" /> : <Activity className="icon spin" />}
            <span>{regionGeoJson ? 'Region Anchored' : 'Scan target missing'}</span>
          </div>
        </div>

        {/* Configuration */}
        <div className="form-group">
          <label><Brain size={14} /> Intelligence Model</label>
          <select 
            className="model-select"
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
          >
            {models.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </div>

        <div className="form-group">
          <label><Calendar size={14} /> Pre-Flood Interval</label>
          <div className="date-range">
            <input 
              type="date" 
              className="date-input" 
              value={startPre} 
              onChange={(e) => setStartPre(e.target.value)}
            />
            <ChevronRight size={14} className="text-dim" />
            <input 
              type="date" 
              className="date-input" 
              value={endPre} 
              onChange={(e) => setEndPre(e.target.value)}
            />
          </div>
        </div>

        <div className="form-group">
          <label><Calendar size={14} /> Post-Flood Interval</label>
          <div className="date-range">
            <input 
              type="date" 
              className="date-input" 
              value={startPost} 
              onChange={(e) => setStartPost(e.target.value)}
            />
            <ChevronRight size={14} className="text-dim" />
            <input 
              type="date" 
              className="date-input" 
              value={endPost} 
              onChange={(e) => setEndPost(e.target.value)}
            />
          </div>
        </div>

        <button 
          className="predict-button"
          onClick={handlePredict}
          disabled={isProcessing || !regionGeoJson}
        >
          {isProcessing ? (
            <><Loader2 className="icon spin" /> Decoding SAR Imagery...</>
          ) : (
            <><Play className="icon" /> Start Deep Scan</>
          )}
        </button>

        {error && (
          <div className="status-item error">
            <AlertCircle className="icon" />
            <span>{error}</span>
          </div>
        )}

        {/* Results Visualization */}
        {riskAssessment && (
          <div className="risk-assessment-results">
            <div className="risk-header">
              <h3 style={{ color: riskAssessment.risk_color }}>
                <Shield className="icon" /> {riskAssessment.risk_level} Impact
              </h3>
              <div className="risk-score">
                {(riskAssessment.overall_risk_score * 100).toFixed(1)}% Vulnerability
              </div>
            </div>

            <div className="results-explanation">
              <strong>Imagery Guide:</strong> High-confidence water detections are highlighted in <span style={{ color: '#ff4b2b', fontWeight: 'bold' }}>Deep Red</span>. Blue outlines indicate the user-selected observation zone.
            </div>

            <div className="risk-section">
              <h4>Vulnerability Profile</h4>
              <div className="risk-grid">
                {Object.entries(riskAssessment.flood_risks).map(([key, val]) => (
                  <div key={key} className="risk-item">
                    <div className="risk-label">
                      <span>{key.replace(/_/g, ' ')}</span>
                      <span>{val}%</span>
                    </div>
                    <div className="risk-bar">
                      <div className="risk-fill" style={{ width: `${val}%`, background: riskAssessment.risk_color }}></div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="risk-section">
              <h4>Operational Intelligence</h4>
              <ul className="recommendations-list">
                {riskAssessment.recommendations.map((rec, i) => <li key={i}>{rec}</li>)}
              </ul>
            </div>

            <div className="pdf-download-section">
              <button 
                className="pdf-download-button"
                onClick={() => {
                  const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8080';
                  window.open(`${apiUrl}/predictions/${riskAssessment.prediction_id || riskAssessment.id}/report`, '_blank');
                }}
              >
                <Download size={16} /> Download Intelligence Briefing
              </button>
            </div>
          </div>
        )}

        {/* Saved Regions */}
        <section className="custom-regions-section">
          <div className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
            <Layers size={14} /> Intelligence Archives
          </div>
          {customRegions.map(reg => (
            <div key={reg.id} className="status-item" style={{ marginBottom: '8px', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '13px' }}>{reg.name || `Region ${reg.id.substring(0, 4)}`}</span>
              <button 
                className="select-region-button"
                style={{ padding: '4px 8px', fontSize: '11px' }}
                onClick={() => onRegionSelect(reg)} // Handle region reload
              >
                Focus
              </button>
            </div>
          ))}
        </section>
      </div>
    </aside>
  );
}
