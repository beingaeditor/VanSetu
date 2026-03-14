/**
 * LocationSearch — Autocomplete search bar with live suggestions
 *
 * Uses Nominatim (OpenStreetMap) geocoding API with:
 * - Debounced typing (300ms) to avoid excessive API calls
 * - Live dropdown suggestions as user types
 * - Keyboard navigation (↑↓ arrows + Enter)
 * - Click-outside dismiss
 * - Delhi-biased search results
 */
import { useState, useEffect, useRef, useCallback } from "react";
import "./LocationSearch.css";

const DEBOUNCE_MS = 300;
const MIN_CHARS = 2;

export default function LocationSearch({ onLocationFound }) {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const wrapperRef = useRef(null);
  const debounceRef = useRef(null);
  const abortRef = useRef(null);

  /* ── Fetch suggestions with debounce ── */
  const fetchSuggestions = useCallback(async (text) => {
    if (text.trim().length < MIN_CHARS) {
      setSuggestions([]);
      setShowDropdown(false);
      return;
    }

    // Cancel any in-flight request
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&limit=6&addressdetails=1&viewbox=76.73,28.87,77.35,28.40&bounded=0&q=${encodeURIComponent(text)}`,
        { signal: controller.signal }
      );
      const data = await res.json();
      const results = data.map((item) => ({
        lat: parseFloat(item.lat),
        lon: parseFloat(item.lon),
        name: item.display_name,
        shortName: buildShortName(item),
        type: item.type || item.class || "",
      }));
      setSuggestions(results);
      setShowDropdown(results.length > 0);
      setActiveIndex(-1);
    } catch (err) {
      if (err.name !== "AbortError") {
        console.error("Search failed:", err);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  /* ── Debounced input handler ── */
  const handleInputChange = (e) => {
    const value = e.target.value;
    setQuery(value);

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      fetchSuggestions(value);
    }, DEBOUNCE_MS);
  };

  /* ── Select a suggestion ── */
  const selectSuggestion = (suggestion) => {
    setQuery(suggestion.shortName);
    setShowDropdown(false);
    setSuggestions([]);
    onLocationFound({
      lat: suggestion.lat,
      lon: suggestion.lon,
      name: suggestion.shortName,
    });
  };

  /* ── Keyboard navigation ── */
  const handleKeyDown = (e) => {
    if (!showDropdown || suggestions.length === 0) {
      if (e.key === "Enter") {
        fetchSuggestions(query);
      }
      return;
    }

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setActiveIndex((prev) =>
          prev < suggestions.length - 1 ? prev + 1 : 0
        );
        break;
      case "ArrowUp":
        e.preventDefault();
        setActiveIndex((prev) =>
          prev > 0 ? prev - 1 : suggestions.length - 1
        );
        break;
      case "Enter":
        e.preventDefault();
        if (activeIndex >= 0 && activeIndex < suggestions.length) {
          selectSuggestion(suggestions[activeIndex]);
        } else if (suggestions.length > 0) {
          selectSuggestion(suggestions[0]);
        }
        break;
      case "Escape":
        setShowDropdown(false);
        setActiveIndex(-1);
        break;
      default:
        break;
    }
  };

  /* ── Click outside to close ── */
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  /* ── Cleanup debounce on unmount ── */
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      if (abortRef.current) abortRef.current.abort();
    };
  }, []);

  const handleClear = () => {
    setQuery("");
    setSuggestions([]);
    setShowDropdown(false);
  };

  return (
    <div className="location-search" ref={wrapperRef}>
      <div className="search-input-wrapper">
        <span className="search-icon" aria-hidden="true">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </span>
        <input
          type="text"
          placeholder="Search places, districts, areas…"
          value={query}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onFocus={() => suggestions.length > 0 && setShowDropdown(true)}
          aria-label="Search location"
          aria-autocomplete="list"
          aria-expanded={showDropdown}
          autoComplete="off"
        />
        {query && (
          <button
            className="search-clear-btn"
            onClick={handleClear}
            aria-label="Clear search"
          >
            ✕
          </button>
        )}
        {loading && <span className="search-spinner" aria-hidden="true" />}
      </div>

      {showDropdown && suggestions.length > 0 && (
        <ul className="search-dropdown" role="listbox">
          {suggestions.map((s, idx) => (
            <li
              key={idx}
              role="option"
              aria-selected={idx === activeIndex}
              className={`search-suggestion ${idx === activeIndex ? "active" : ""}`}
              onClick={() => selectSuggestion(s)}
              onMouseEnter={() => setActiveIndex(idx)}
            >
              <span className="suggestion-icon" aria-hidden="true">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                  <circle cx="12" cy="10" r="3" />
                </svg>
              </span>
              <div className="suggestion-text">
                <span className="suggestion-name">{s.shortName}</span>
                <span className="suggestion-detail">{s.name}</span>
              </div>
            </li>
          ))}
          <li className="search-attribution">
            Powered by OpenStreetMap Nominatim
          </li>
        </ul>
      )}
    </div>
  );
}

/* ── Helper: build a concise label ── */
function buildShortName(item) {
  const addr = item.address || {};
  const parts = [];

  // Prefer specific place names
  const placeName =
    addr.neighbourhood ||
    addr.suburb ||
    addr.village ||
    addr.town ||
    addr.city_district ||
    addr.hamlet ||
    "";

  if (placeName) parts.push(placeName);

  const city = addr.city || addr.state_district || addr.county || "";
  if (city && city !== placeName) parts.push(city);

  const state = addr.state || "";
  if (state && state !== city) parts.push(state);

  if (parts.length === 0) {
    // Fallback: use first two comma-parts of display_name
    return item.display_name.split(",").slice(0, 2).join(",").trim();
  }

  return parts.slice(0, 3).join(", ");
}