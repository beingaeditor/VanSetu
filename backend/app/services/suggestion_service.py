"""
Community Suggestions Service — Corridor-level community participation

This service handles:
- Storing and retrieving community suggestions for corridors
- Upvoting suggestions
- IP-based rate limiting for abuse prevention

DATA MODEL (MongoDB collection: corridor_suggestions):
{
    "_id": "ObjectId",
    "corridor_id": "string",
    "text": "string",
    "upvotes": 0,
    "created_at": "ISO-8601",
    "client_ip": "string"  # For rate limiting only
}

DESIGN PRINCIPLES:
- No authentication required
- Simple IP-based rate limiting
- Suggestions are advisory only, not affecting corridor ranking
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from collections import defaultdict
import threading

from bson import ObjectId
from pymongo import MongoClient, DESCENDING, ASCENDING
from pymongo.errors import ConnectionFailure

from app.config import Settings


class RateLimiter:
    """
    Simple in-memory rate limiter for IP-based throttling.
    
    Limits:
    - Suggestions: Max 3 per IP per corridor per hour
    - Upvotes: Max 10 per IP per hour
    """
    
    def __init__(self):
        self._suggestion_counts: Dict[str, List[datetime]] = defaultdict(list)
        self._upvote_counts: Dict[str, List[datetime]] = defaultdict(list)
        self._lock = threading.Lock()
        
        # Rate limit settings
        self.suggestion_limit = 3  # per IP per corridor per hour
        self.upvote_limit = 10  # per IP per hour
        self.window_seconds = 3600  # 1 hour
    
    def _cleanup_old_entries(self, entries: List[datetime]) -> List[datetime]:
        """Remove entries older than the rate limit window."""
        cutoff = datetime.utcnow() - timedelta(seconds=self.window_seconds)
        return [e for e in entries if e > cutoff]
    
    def check_suggestion_limit(self, client_ip: str, corridor_id: str) -> tuple[bool, str]:
        """
        Check if IP can submit a suggestion for this corridor.
        Returns (allowed, message).
        """
        key = f"{client_ip}:{corridor_id}"
        
        with self._lock:
            self._suggestion_counts[key] = self._cleanup_old_entries(
                self._suggestion_counts[key]
            )
            
            if len(self._suggestion_counts[key]) >= self.suggestion_limit:
                return False, f"Rate limit exceeded. You can submit up to {self.suggestion_limit} suggestions per corridor per hour."
            
            return True, "OK"
    
    def record_suggestion(self, client_ip: str, corridor_id: str):
        """Record a suggestion submission."""
        key = f"{client_ip}:{corridor_id}"
        
        with self._lock:
            self._suggestion_counts[key].append(datetime.utcnow())
    
    def check_upvote_limit(self, client_ip: str) -> tuple[bool, str]:
        """
        Check if IP can upvote.
        Returns (allowed, message).
        """
        with self._lock:
            self._upvote_counts[client_ip] = self._cleanup_old_entries(
                self._upvote_counts[client_ip]
            )
            
            if len(self._upvote_counts[client_ip]) >= self.upvote_limit:
                return False, f"Rate limit exceeded. You can upvote up to {self.upvote_limit} times per hour."
            
            return True, "OK"
    
    def record_upvote(self, client_ip: str):
        """Record an upvote."""
        with self._lock:
            self._upvote_counts[client_ip].append(datetime.utcnow())


class SuggestionService:
    """
    Service for managing community suggestions for corridors.
    
    Uses MongoDB for persistence with in-memory rate limiting.
    """
    
    # Collection name
    COLLECTION_NAME = "corridor_suggestions"
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: Optional[MongoClient] = None
        self._db = None
        self._collection = None
        self._connected = False
        
        # Rate limiter instance
        self.rate_limiter = RateLimiter()
        
        # Connect to MongoDB
        self._connect()
    
    def _connect(self):
        """Connect to MongoDB."""
        mongo_uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
        db_name = os.environ.get("MONGODB_DB", "urban_green_corridors")
        
        try:
            self._client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            # Test connection
            self._client.admin.command('ping')
            
            self._db = self._client[db_name]
            self._collection = self._db[self.COLLECTION_NAME]
            
            # Create indexes
            self._collection.create_index("corridor_id")
            self._collection.create_index("created_at")
            self._collection.create_index([
                ("corridor_id", ASCENDING),
                ("upvotes", DESCENDING),
                ("created_at", ASCENDING)
            ])
            
            self._connected = True
            print(f"✅ Connected to MongoDB: {db_name}/{self.COLLECTION_NAME}")
            
        except ConnectionFailure as e:
            print(f"⚠️ MongoDB connection failed: {e}")
            print("   Suggestion feature will be unavailable")
            self._connected = False
    
    @property
    def is_connected(self) -> bool:
        """Check if MongoDB connection is active."""
        return self._connected and self._client is not None
    
    def create_suggestion(
        self, 
        corridor_id: str, 
        text: str, 
        client_ip: str
    ) -> Dict[str, Any]:
        """
        Create a new suggestion for a corridor.
        
        Args:
            corridor_id: The corridor UUID
            text: Suggestion text (max 300 chars)
            client_ip: Client IP for rate limiting
            
        Returns:
            Created suggestion document
            
        Raises:
            ValueError: If validation fails
            RuntimeError: If rate limited or DB unavailable
        """
        if not self.is_connected:
            raise RuntimeError("Database not available")
        
        # Validate text
        text = text.strip() if text else ""
        if not text:
            raise ValueError("Suggestion text cannot be empty")
        if len(text) > 300:
            raise ValueError("Suggestion text cannot exceed 300 characters")
        if len(text) < 3:
            raise ValueError("Suggestion text must be at least 3 characters")
        
        # Basic spam check
        if self._is_spam(text):
            raise ValueError("Suggestion appears to be spam or invalid")
        
        # Check rate limit
        allowed, message = self.rate_limiter.check_suggestion_limit(client_ip, corridor_id)
        if not allowed:
            raise RuntimeError(message)
        
        # Create document
        doc = {
            "corridor_id": corridor_id,
            "text": text,
            "upvotes": 0,
            "created_at": datetime.utcnow().isoformat(),
            "client_ip": client_ip  # Stored for rate limiting, not displayed
        }
        
        result = self._collection.insert_one(doc)
        doc["_id"] = str(result.inserted_id)
        
        # Record for rate limiting
        self.rate_limiter.record_suggestion(client_ip, corridor_id)
        
        # Return without client_ip
        return {
            "id": doc["_id"],
            "corridor_id": doc["corridor_id"],
            "text": doc["text"],
            "upvotes": doc["upvotes"],
            "created_at": doc["created_at"]
        }
    
    def _is_spam(self, text: str) -> bool:
        """Basic spam detection."""
        # Check for repetitive characters
        if len(set(text.lower())) < 3:
            return True
        
        # Check for all caps (if long enough)
        if len(text) > 20 and text.isupper():
            return True
        
        # Check for excessive repetition
        words = text.lower().split()
        if len(words) > 3 and len(set(words)) == 1:
            return True
        
        return False
    
    def get_suggestions(self, corridor_id: str) -> List[Dict[str, Any]]:
        """
        Get all suggestions for a corridor.
        
        Sorted by:
        1. Upvotes (descending)
        2. Created time (ascending, older first)
        
        Args:
            corridor_id: The corridor UUID
            
        Returns:
            List of suggestion documents
        """
        if not self.is_connected:
            return []
        
        cursor = self._collection.find(
            {"corridor_id": corridor_id}
        ).sort([
            ("upvotes", DESCENDING),
            ("created_at", ASCENDING)
        ])
        
        suggestions = []
        for doc in cursor:
            suggestions.append({
                "id": str(doc["_id"]),
                "text": doc["text"],
                "upvotes": doc.get("upvotes", 0),
                "created_at": doc["created_at"]
            })
        
        return suggestions
    
    def upvote_suggestion(
        self, 
        suggestion_id: str, 
        client_ip: str
    ) -> Dict[str, Any]:
        """
        Upvote a suggestion.
        
        Args:
            suggestion_id: The suggestion ObjectId
            client_ip: Client IP for rate limiting
            
        Returns:
            Updated suggestion document
            
        Raises:
            ValueError: If suggestion not found
            RuntimeError: If rate limited or DB unavailable
        """
        if not self.is_connected:
            raise RuntimeError("Database not available")
        
        # Check rate limit
        allowed, message = self.rate_limiter.check_upvote_limit(client_ip)
        if not allowed:
            raise RuntimeError(message)
        
        try:
            obj_id = ObjectId(suggestion_id)
        except Exception:
            raise ValueError("Invalid suggestion ID")
        
        # Increment upvotes
        result = self._collection.find_one_and_update(
            {"_id": obj_id},
            {"$inc": {"upvotes": 1}},
            return_document=True
        )
        
        if result is None:
            raise ValueError("Suggestion not found")
        
        # Record for rate limiting
        self.rate_limiter.record_upvote(client_ip)
        
        return {
            "id": str(result["_id"]),
            "text": result["text"],
            "upvotes": result.get("upvotes", 0),
            "created_at": result["created_at"]
        }
    
    def get_suggestion_count(self, corridor_id: str) -> int:
        """Get count of suggestions for a corridor."""
        if not self.is_connected:
            return 0
        return self._collection.count_documents({"corridor_id": corridor_id})
    
    def get_total_upvotes(self, corridor_id: str) -> int:
        """Get total upvotes across all suggestions for a corridor."""
        if not self.is_connected:
            return 0
        
        pipeline = [
            {"$match": {"corridor_id": corridor_id}},
            {"$group": {"_id": None, "total": {"$sum": "$upvotes"}}}
        ]
        result = list(self._collection.aggregate(pipeline))
        return result[0]["total"] if result else 0

    def upvote_corridor(self, corridor_id: str, client_ip: str) -> Dict[str, Any]:
        """
        Upvote a corridor.
        
        Args:
            corridor_id: The corridor UUID
            client_ip: Client IP for rate limiting
            
        Returns:
            Updated corridor upvote count
            
        Raises:
            RuntimeError: If rate limited or DB unavailable
        """
        if not self.is_connected:
            raise RuntimeError("Database not available")
        
        # Check rate limit (reuse upvote limit)
        allowed, message = self.rate_limiter.check_upvote_limit(client_ip)
        if not allowed:
            raise RuntimeError(message)
        
        # Use corridor_upvotes collection
        upvotes_collection = self._db["corridor_upvotes"]
        
        # Upsert the corridor upvote count
        result = upvotes_collection.find_one_and_update(
            {"corridor_id": corridor_id},
            {"$inc": {"upvotes": 1}},
            upsert=True,
            return_document=True
        )
        
        # Record for rate limiting
        self.rate_limiter.record_upvote(client_ip)
        
        return {
            "corridor_id": corridor_id,
            "upvotes": result.get("upvotes", 1)
        }
    
    def get_corridor_upvotes(self, corridor_id: str) -> int:
        """Get upvote count for a corridor."""
        if not self.is_connected:
            return 0
        
        upvotes_collection = self._db["corridor_upvotes"]
        doc = upvotes_collection.find_one({"corridor_id": corridor_id})
        return doc.get("upvotes", 0) if doc else 0

    def get_all_suggestions(self) -> list:
        """Get all suggestions across all corridors (for admin review)."""
        if not self.is_connected:
            return []
        
        try:
            cursor = self._collection.find(
                {},
                {"_id": 1, "corridor_id": 1, "text": 1, "upvotes": 1, "created_at": 1}
            ).sort("created_at", -1).limit(200)
            
            results = []
            for doc in cursor:
                results.append({
                    "id": str(doc["_id"]),
                    "corridor_id": doc.get("corridor_id", ""),
                    "text": doc.get("text", ""),
                    "upvotes": doc.get("upvotes", 0),
                    "created_at": doc.get("created_at", ""),
                })
            return results
        except Exception:
            return []
