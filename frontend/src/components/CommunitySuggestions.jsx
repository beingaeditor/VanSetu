/**
 * CommunitySuggestions — Community participation section for corridor panel
 * 
 * Allows users to:
 * - Submit suggestions for a corridor
 * - View community suggestions
 * 
 * Rate limited:
 * - 3 suggestions per corridor per hour
 */
import { useState, useEffect, useCallback } from 'react';
import { suggestionsApi } from '../api';
import './CommunitySuggestions.css';

const MAX_CHARS = 300;
const MIN_CHARS = 3;

export default function CommunitySuggestions({ corridorId }) {
  // Suggestions state
  const [suggestions, setSuggestions] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Input state
  const [inputText, setInputText] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  // Fetch suggestions when corridor changes
  const fetchSuggestions = useCallback(async () => {
    if (!corridorId) return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await suggestionsApi.list(corridorId);
      setSuggestions(response.data.suggestions || []);
    } catch (err) {
      console.error('Failed to fetch suggestions:', err);
      setError('Could not load suggestions');
      setSuggestions([]);
    } finally {
      setIsLoading(false);
    }
  }, [corridorId]);

  useEffect(() => {
    fetchSuggestions();
    // Reset state when corridor changes
    setInputText('');
    setSubmitError(null);
  }, [corridorId, fetchSuggestions]);

  // Handle input change
  const handleInputChange = (e) => {
    const text = e.target.value;
    if (text.length <= MAX_CHARS) {
      setInputText(text);
      setSubmitError(null);
    }
  };

  // Handle suggestion submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    const trimmedText = inputText.trim();
    if (trimmedText.length < MIN_CHARS) {
      setSubmitError(`Suggestion must be at least ${MIN_CHARS} characters`);
      return;
    }
    
    setIsSubmitting(true);
    setSubmitError(null);
    
    try {
      const response = await suggestionsApi.create(corridorId, trimmedText);
      // Add new suggestion to the top of the list (optimistic)
      setSuggestions(prev => [response.data, ...prev]);
      setInputText('');
    } catch (err) {
      console.error('Failed to submit suggestion:', err);
      const message = err.response?.data?.detail || 'Failed to submit suggestion';
      setSubmitError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Character count display
  const charCount = inputText.length;
  const trimmedLength = inputText.trim().length;
  const isValidLength = trimmedLength >= MIN_CHARS && charCount <= MAX_CHARS;
  const canSubmit = isValidLength && !isSubmitting;

  return (
    <div className="community-suggestions">
      <h3 className="suggestions-header">
        <span className="suggestions-icon">🗣️</span>
        Community Suggestions
      </h3>
      
      {/* Suggestion Input */}
      <form className="suggestion-input-form" onSubmit={handleSubmit}>
        <textarea
          className="suggestion-textarea"
          placeholder="Suggest an improvement for this corridor…"
          value={inputText}
          onChange={handleInputChange}
          disabled={isSubmitting}
          rows={3}
        />
        <div className="suggestion-input-footer">
          <span className={`char-counter ${charCount > MAX_CHARS - 50 ? 'warning' : ''} ${charCount >= MAX_CHARS ? 'error' : ''}`}>
            {charCount}/{MAX_CHARS}
          </span>
          <button 
            type="submit" 
            className="submit-btn"
            disabled={!canSubmit}
          >
            {isSubmitting ? 'Submitting...' : 'Submit'}
          </button>
        </div>
        {submitError && (
          <div className="suggestion-error">{submitError}</div>
        )}
        {!submitError && charCount > 0 && trimmedLength < MIN_CHARS && (
          <div className="suggestion-hint">Type at least {MIN_CHARS} characters to submit</div>
        )}
      </form>
      
      {/* Suggestions List */}
      <div className="suggestions-list">
        {isLoading ? (
          <div className="suggestions-loading">Loading suggestions...</div>
        ) : error ? (
          <div className="suggestions-error">{error}</div>
        ) : suggestions.length === 0 ? (
          <div className="suggestions-empty">
            No community suggestions yet. Be the first.
          </div>
        ) : (
          suggestions.map(suggestion => (
            <div key={suggestion.id} className="suggestion-item">
              <p className="suggestion-text">{suggestion.text}</p>
              <div className="suggestion-footer">
                <span className="suggestion-time">
                  {formatRelativeTime(suggestion.created_at)}
                </span>
              </div>
            </div>
          ))
        )}
      </div>
      
      {/* Advisory note */}
      <div className="suggestions-advisory">
        Community suggestions are advisory and do not affect corridor ranking.
      </div>
    </div>
  );
}

/**
 * Format ISO timestamp to relative time
 */
function formatRelativeTime(isoString) {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  
  return date.toLocaleDateString();
}
