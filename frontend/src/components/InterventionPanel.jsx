/**
 * InterventionPanel — Right-side sliding panel for corridor intervention suggestions
 * 
 * Displays when a corridor is clicked:
 * - Corridor type classification
 * - Recommended green interventions
 * - Human-readable rationale
 * - Upvote button for community support
 * - Community suggestions
 * 
 * Designed for clarity, not density. No numbers, equations, or jargon.
 */
import { useEffect, useRef, useState } from 'react';
import './InterventionPanel.css';
import CommunitySuggestions from './CommunitySuggestions';
import { suggestionsApi } from '../api';

// Keyword → icon mapping for dynamic intervention names
const ICON_KEYWORDS = [
  [/tree|canopy|neem|peepal|banyan|albizia|cassia|arjuna/i, "🌳"],
  [/shade|cool|mist|reflective|solar/i, "☂️"],
  [/hedge|buffer|screen|bamboo|filter|dust/i, "🌲"],
  [/pocket|park|garden|micro-forest|miyawaki/i, "🏞️"],
  [/cycle|pedestrian|walkway|boulevard/i, "🚴"],
  [/wall|vertical|façade|creeper|climbing/i, "🌿"],
  [/rain|bioswale|stormwater|drain/i, "💧"],
  [/community|adopt|school|citizen|RWA/i, "🤝"],
  [/AQI|monitor|display|sensor/i, "📊"],
  [/food|market|composting/i, "🌱"],
];

function interventionIcon(text) {
  for (const [re, icon] of ICON_KEYWORDS) {
    if (re.test(text)) return icon;
  }
  return "🌱";
}

// Type labels for display
const TYPE_LABELS = {
  "heat_dominated": "Heat-Dominated Corridor",
  "pollution_dominated": "Air Quality Corridor",
  "green_deficit": "Green Connectivity Corridor",
  "mixed_exposure": "Multi-Challenge Corridor"
};

export default function InterventionPanel({ corridor, onClose }) {
  const panelRef = useRef(null);
  
  // Upvote state
  const [upvotes, setUpvotes] = useState(0);
  const [hasUpvoted, setHasUpvoted] = useState(false);
  const [isUpvoting, setIsUpvoting] = useState(false);
  
  const props = corridor?.properties || {};
  const corridorId = props.id || corridor?.id || null;
  
  // Focus trap and escape key handler
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [onClose]);
  
  // Fetch upvotes when corridor changes
  useEffect(() => {
    if (!corridorId) return;
    
    setHasUpvoted(false);
    setUpvotes(0);
    
    suggestionsApi.getCorridorUpvotes(corridorId)
      .then(res => setUpvotes(res.data.upvotes || 0))
      .catch(err => console.error('Failed to fetch upvotes:', err));
  }, [corridorId]);
  
  // Handle upvote
  const handleUpvote = async () => {
    if (hasUpvoted || isUpvoting || !corridorId) return;
    
    setIsUpvoting(true);
    // Optimistic update
    setUpvotes(prev => prev + 1);
    setHasUpvoted(true);
    
    try {
      const res = await suggestionsApi.upvoteCorridor(corridorId);
      setUpvotes(res.data.upvotes);
    } catch (err) {
      console.error('Failed to upvote:', err);
      // Rollback
      setUpvotes(prev => prev - 1);
      setHasUpvoted(false);
    } finally {
      setIsUpvoting(false);
    }
  };
  
  if (!corridor) return null;
  
  const corridorType = props.corridor_type || 'mixed_exposure';
  const interventions = props.recommended_interventions || [];
  const rationale = props.intervention_rationale || '';
  const typeIcon = props.corridor_type_icon || '🛤️';
  const typeColor = props.corridor_type_color || '#fc8d59';
  const roadName = props.name || 'Selected Corridor';
  
  return (
    <div className="intervention-panel" ref={panelRef}>
      {/* Close button */}
      <button 
        className="panel-close-btn" 
        onClick={onClose}
        aria-label="Close panel"
      >
        ✕
      </button>
      
      {/* Header */}
      <div className="panel-header">
        <div className="panel-icon" style={{ background: typeColor }}>
          {typeIcon}
        </div>
        <div className="panel-title">
          <h2>{roadName}</h2>
          <span className="panel-subtitle">Corridor Selected</span>
        </div>
      </div>
      
      {/* Upvote Button for Corridor */}
      <div className="corridor-upvote-section">
        <button
          className={`corridor-upvote-btn ${hasUpvoted ? 'upvoted' : ''}`}
          onClick={handleUpvote}
          disabled={hasUpvoted || isUpvoting}
          title={hasUpvoted ? 'You supported this corridor' : 'Support this corridor'}
        >
          <span className="upvote-icon">👍</span>
          <span className="upvote-text">
            {hasUpvoted ? 'Supported' : 'Support This Corridor'}
          </span>
          <span className="upvote-count">{upvotes}</span>
        </button>
      </div>
      
      {/* Type Badge */}
      <div className="corridor-type-section">
        <div 
          className="corridor-type-badge"
          style={{ borderColor: typeColor, color: typeColor }}
        >
          {TYPE_LABELS[corridorType] || corridorType}
        </div>
      </div>
      
      {/* Interventions */}
      <div className="interventions-section">
        <h3>Suggested Interventions</h3>
        <div className="interventions-list">
          {interventions.map((intervention, idx) => (
            <div key={idx} className="intervention-item">
              <span className="intervention-icon">
                {interventionIcon(intervention)}
              </span>
              <span className="intervention-text">{intervention}</span>
            </div>
          ))}
        </div>
      </div>
      
      {/* Rationale */}
      <div className="rationale-section">
        <h3>Why This Works</h3>
        <p className="rationale-text">{rationale}</p>
      </div>
      
      {/* Community Suggestions */}
      {corridorId ? (
        <CommunitySuggestions corridorId={corridorId} />
      ) : null}
      
      {/* Footer hint */}
      <div className="panel-footer">
        <span className="footer-hint">Press ESC or click ✕ to return to map</span>
      </div>
    </div>
  );
}
