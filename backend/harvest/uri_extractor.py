"""
Extract URIs from Linked Art JSON-LD records.

This module provides functions to extract various types of URIs from Linked Art JSON:
- Creator/person URIs (from object records)
- VisualItem URIs (from object records)
- External URIs (Wikidata, Getty ULAN, Library of Congress) - works on both object and person records
"""

from typing import Any, Dict, List, Optional, Set


def _classify_uri_type(uri: str) -> str:
    """
    Classify a URI by its domain/pattern.
    
    Returns: 'wikidata', 'getty_ulan', 'loc', 'yale_person', 'yale_visual_item', or 'other'
    """
    if not uri:
        return 'other'
    
    uri_lower = uri.lower()
    
    # Person records
    if 'lux/person' in uri_lower or 'lux/agt' in uri_lower:
        return 'person'
    
    # VisualItem records
    if 'lux/vis' in uri_lower:
        return 'yvisual_item'
    
    # Wikidata
    if 'wikidata.org' in uri_lower:
        return 'wikidata'
    
    # Getty ULAN
    if 'vocab.getty.edu/ulan' in uri_lower:
        return 'getty_ulan'
    
    # Library of Congress
    if 'id.loc.gov' in uri_lower or 'lccn.loc.gov' in uri_lower:
        return 'loc'
    
    return 'other'


def _is_external_uri(uri: str) -> bool:
    """Check if a URI is an external URI (not a Yale URI)."""
    if not uri:
        return False
    
    uri_type = _classify_uri_type(uri)
    return uri_type in ['wikidata', 'getty_ulan', 'loc', 'person', 'visual_item']


def _extract_uris_recursive(obj: Any, found_uris: Set[str], path: str = "") -> None:
    """
    Recursively traverse a JSON structure to find all URIs.
    
    Args:
        obj: The JSON object to traverse (dict, list, or primitive)
        found_uris: Set to store unique URIs found
        path: Current path in the JSON structure (for debugging)
    """
    if isinstance(obj, dict):
        # Check if this dict has an 'id' field that's a URI
        if 'id' in obj:
            uri = obj['id']
            if isinstance(uri, str) and (uri.startswith('http://') or uri.startswith('https://')):
                found_uris.add(uri)
        
        # Recursively check all values
        for key, value in obj.items():
            _extract_uris_recursive(value, found_uris, f"{path}.{key}" if path else key)
    
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _extract_uris_recursive(item, found_uris, f"{path}[{i}]" if path else f"[{i}]")

def extract_public_location_string(linked_art_json: Dict[str, Any]) -> Optional[str]:
    """
    Extract the public location string from the linked_art_json.
    """
    public_location_string = None
    for ref in linked_art_json.get('referred_to_by', []):
        if ref.get('type') == 'LinguisticObject':
            content = ref.get('content', '')
            classified_as = ref.get('classified_as', [])
            for cls in classified_as:
                if isinstance(cls, dict):
                    if cls.get('id') == 'http://vocab.getty.edu/aat/300133046':
                        public_location_string = content
                        break
    return public_location_string

def extract_creator_uris(linked_art_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract artist/person URIs from object's produced_by.part[].carried_out_by[].
    
    This function is specific to object records (not person records).
    """
    creator_uris = []
    produced_by = linked_art_json.get('produced_by', {})
    
    # Handle both direct 'part' array and nested structure
    parts = produced_by.get('part', []) if isinstance(produced_by, dict) else []
    
    for part in parts:
        if not isinstance(part, dict):
            continue
        
        carried_out_by_list = part.get('carried_out_by', [])
        if not isinstance(carried_out_by_list, list):
            continue
        
        for carried_out_by in carried_out_by_list:
            if not isinstance(carried_out_by, dict):
                continue
            
            creator_id = carried_out_by.get('id')
            if creator_id:
                creator_uris.append({
                    'uri': creator_id,
                    'type': 'yale_person',  # These are Yale person URIs
                    'context': 'produced_by.part[].carried_out_by[]'
                })
    
    return creator_uris


def extract_visual_item_uris(linked_art_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract VisualItem URIs from shows[] field.
    
    This function is specific to object records.
    """
    visual_item_uris = []
    shows = linked_art_json.get('shows', [])
    
    if not isinstance(shows, list):
        return visual_item_uris
    
    for show in shows:
        if not isinstance(show, dict):
            continue
        
        # Check if it's a VisualItem (either by type or by URI pattern)
        show_type = show.get('type', '')
        show_id = show.get('id', '')
        
        if show_type == 'VisualItem' or 'lux/vis' in show_id.lower():
            visual_item_uris.append({
                'uri': show_id,
                'type': 'yale_visual_item',
                'context': 'shows[]'
            })
    
    return visual_item_uris


def extract_external_uris(linked_art_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract external URIs (Wikidata, Getty ULAN, Library of Congress) from any Linked Art JSON.
    
    This function works on both object records and person records.
    It searches in:
    - equivalent[] arrays (most common location)
    - Recursively throughout the JSON structure
    
    Args:
        linked_art_json: Any Linked Art JSON record (object, person, etc.)
    
    Returns:
        List of dicts with 'uri', 'type', and 'context' keys
    """
    external_uris = []
    found_uris: Set[str] = set()
    
    # First, check the equivalent[] array (most common place for external links)
    equivalents = linked_art_json.get('equivalent', [])
    if isinstance(equivalents, list):
        for equiv in equivalents:
            # equivalent can be a dict with 'id' or just a string URI
            if isinstance(equiv, dict):
                uri = equiv.get('id')
            elif isinstance(equiv, str):
                uri = equiv
            else:
                continue
            
            if uri and _is_external_uri(uri):
                found_uris.add(uri)
                external_uris.append({
                    'uri': uri,
                    'type': _classify_uri_type(uri),
                    'context': 'equivalent[]'
                })
    
    # Also recursively search the entire JSON structure
    # (in case external URIs are nested elsewhere)
    _extract_uris_recursive(linked_art_json, found_uris)
    
    # Add any external URIs found recursively that weren't already in equivalent[]
    for uri in found_uris:
        if _is_external_uri(uri):
            # Check if we already added this URI from equivalent[]
            if not any(existing['uri'] == uri for existing in external_uris):
                external_uris.append({
                    'uri': uri,
                    'type': _classify_uri_type(uri),
                    'context': 'nested_structure'
                })
    
    return external_uris

def _image_url_from_representation(representation: Any) -> Optional[str]:
    """First image access URL from a representation list (or single dict) on HumanMadeObject or VisualItem."""
    if representation is None:
        return None
    if isinstance(representation, dict):
        representation = [representation]
    if not isinstance(representation, list):
        return None

    for rep in representation:
        if not isinstance(rep, dict):
            continue

        digitally_shown_by = rep.get("digitally_shown_by", [])
        if not isinstance(digitally_shown_by, list):
            continue

        for dobj in digitally_shown_by:
            if not isinstance(dobj, dict):
                continue
            if dobj.get("type") != "DigitalObject":
                continue

            access_point = dobj.get("access_point", [])
            if not isinstance(access_point, list):
                continue

            for ap in access_point:
                if isinstance(ap, dict) and ap.get("id"):
                    return ap.get("id")
    return None


def extract_image_url(linked_art_json: Dict[str, Any]) -> Optional[str]:
    """
    Extract an image URL from a HumanMadeObject or VisualItem Linked Art record.

    Tries ``representation`` on the root, then embedded ``shows[]`` VisualItems (some records
    only attach ``digitally_shown_by`` on the VisualItem, not on the object).
    """
    url = _image_url_from_representation(linked_art_json.get("representation"))
    if url:
        return url

    shows = linked_art_json.get("shows", [])
    if not isinstance(shows, list):
        return None

    for show in shows:
        if not isinstance(show, dict):
            continue
        st = show.get("type", "")
        sid = show.get("id", "") or ""
        if st == "VisualItem" or "lux/vis" in sid.lower():
            url = _image_url_from_representation(show.get("representation"))
            if url:
                return url
    return None
        
    
def extract_all_uris(linked_art_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Comprehensive extraction of all URIs from an object record.
    
    This combines creator URIs, VisualItem URIs, and external URIs.
    Note: This is primarily for object records. For person records,
    use extract_external_uris() directly.
    """
    all_uris = []
    all_uris.extend(extract_creator_uris(linked_art_json))
    all_uris.extend(extract_visual_item_uris(linked_art_json))
    all_uris.extend(extract_external_uris(linked_art_json))
    return all_uris