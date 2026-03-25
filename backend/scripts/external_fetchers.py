"""
External data fetchers for enriching object records with external knowledge.

This module fetches data from:
- Yale Linked Art person/creator records
- Yale Linked Art VisualItem records
- Wikidata
- Getty ULAN
- Library of Congress
"""

from typing import Dict, Any, List, Optional
import requests
import time
from backend.scripts.uri_extractor import extract_external_uris

# Wikidata and many APIs require a User-Agent; without it requests get 403.
REQUESTS_HEADERS = {
    "User-Agent": "YaleThesisEnrichment/1.0 (https://github.com; research/thesis)"
}


def fetch_artist(uri: str) -> Dict[str, Any]:
    """
    Fetch a Yale Linked Art person/creator record and extract relevant data.
    
    Args:
        uri: Full URI to the person record (e.g., "https://media.art.yale.edu/content/lux/person/123")
    
    Returns:
        Dictionary with name, biography, external_uris, and full_record
    """
    # Ensure URI ends with .json
    if not uri.endswith('.json'):
        uri = uri.rstrip('/') + '.json'
    
    # Fetch the person record
    try:
        response = requests.get(uri, timeout=10)
        response.raise_for_status()
        person_json = response.json()
    except Exception as e:
        err_msg = str(e).strip() or f"{type(e).__name__}"
        return {
            'name': None,
            'biography': None,
            'external_uris': [],
            'full_record': None,
            'error': err_msg
        }
    
    # Extract name
    name = person_json.get('_label', '').replace('Artist: ', '').replace('Person: ', '')
    
    # Extract biography from referred_to_by[]
    biography_parts = []
    for ref in person_json.get('referred_to_by', []):
        if isinstance(ref, dict):
            content = ref.get('content', '')
            if content:
                biography_parts.append(content)
    biography = ' '.join(biography_parts) if biography_parts else None
    
    # Extract external URIs (Wikidata, Getty, LoC) from the person record
    external_uris = extract_external_uris(person_json)
    
    return {
        'name': name,
        'biography': biography,
        'external_uris': external_uris,
        'full_record': person_json,
        'error': None
    }


def fetch_visual_item(uri: str) -> Dict[str, Any]:
    """
    Fetch a Yale Linked Art VisualItem record and extract style, places, and subjects.
    
    Args:
        uri: Full URI to the VisualItem record (e.g., "https://media.art.yale.edu/content/lux/vis/52939")
    
    Returns:
        Dictionary with style_classifications, depicted_places, subject_matter, extracted_text, and full_record
    """
    # Ensure URI ends with .json
    if not uri.endswith('.json'):
        uri = uri.rstrip('/') + '.json'

    # Fetch the visual item record
    try:
        response = requests.get(uri, timeout=10)
        response.raise_for_status()
        visual_item_json = response.json()
    except Exception as e:
        err_msg = str(e).strip() or f"{type(e).__name__}"
        return {
            'style_classifications': [],
            'depicted_places': [],
            'subject_matter': [],
            'extracted_text': None,
            'full_record': None,
            'error': err_msg
        }
    
    # Extract style classifications from classified_as[]
    styles = []
    for cls in visual_item_json.get('classified_as', []):
        if isinstance(cls, dict):
            label = cls.get('_label', '')
            # Check if it's a style (has "Style" in its classification chain)
            classified_as = cls.get('classified_as', [])
            for sub_cls in classified_as:
                if isinstance(sub_cls, dict) and 'style' in sub_cls.get('_label', '').lower():
                    if label:
                        styles.append(label)
    
    # Extract depicted places from represents[]
    places = []
    for rep in visual_item_json.get('represents', []):
        if isinstance(rep, dict):
            label = rep.get('_label', '')
            if label:
                places.append(label)
    
    # Extract subject matter from about[]
    subjects = []
    for about in visual_item_json.get('about', []):
        if isinstance(about, dict):
            label = about.get('_label', '')
            if label:
                subjects.append(label)
    
    # Combine into text for embeddings
    text_parts = []
    if styles:
        text_parts.append(f"Style: {', '.join(styles)}")
    if places:
        text_parts.append(f"Depicted: {', '.join(places)}")
    if subjects:
        text_parts.append(f"Subjects: {', '.join(subjects)}")
    extracted_text = '. '.join(text_parts) if text_parts else None
    
    return {
        'style_classifications': styles,
        'depicted_places': places,
        'subject_matter': subjects,
        'extracted_text': extracted_text,
        'full_record': visual_item_json,
        'error': None
    }


def fetch_wikidata(wikidata_id: str) -> Dict[str, Any]:
    """
    Fetch data from Wikidata API.
    
    Args:
        wikidata_id: Wikidata entity ID (e.g., "Q123" or full URI "http://www.wikidata.org/entity/Q123")
    
    Returns:
        Dictionary with description, biography, and full_data
    """
    # Extract ID from URI if needed
    if '/' in wikidata_id:
        wikidata_id = wikidata_id.split('/')[-1]
    if wikidata_id.startswith('Q'):
        entity_id = wikidata_id
    else:
        return {
            'description': None,
            'biography': None,
            'full_data': None,
            'error': 'Invalid Wikidata ID format'
        }
    
    # Wikidata API endpoint (requires User-Agent or returns 403)
    url = f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json"
    
    try:
        response = requests.get(url, timeout=10, headers=REQUESTS_HEADERS)
        response.raise_for_status()
        data = response.json()
        
        # Extract entity data
        entity = data.get('entities', {}).get(entity_id, {})
        
        # Extract description (English)
        description = None
        descriptions = entity.get('descriptions', {})
        if 'en' in descriptions:
            description = descriptions['en'].get('value', '')
        
        # Extract biography from claims (simplified - just get some text)
        biography_parts = []
        claims = entity.get('claims', {})
        
        # Get birth date (P569)
        if 'P569' in claims:
            birth_claim = claims['P569'][0]
            birth_date = birth_claim.get('mainsnak', {}).get('datavalue', {}).get('value', {}).get('time', '')
            if birth_date:
                biography_parts.append(f"Born: {birth_date}")
        
        # Get death date (P570)
        if 'P570' in claims:
            death_claim = claims['P570'][0]
            death_date = death_claim.get('mainsnak', {}).get('datavalue', {}).get('value', {}).get('time', '')
            if death_date:
                biography_parts.append(f"Died: {death_date}")
        
        biography = '. '.join(biography_parts) if biography_parts else None
        
        return {
            'description': description,
            'biography': biography,
            'full_data': data,
            'error': None
        }
    except Exception as e:
        return {
            'description': None,
            'biography': None,
            'full_data': None,
            'error': str(e)
        }


def fetch_getty_ulan(ulan_id: str) -> Dict[str, Any]:
    """
    Fetch data from Getty ULAN (Union List of Artist Names).
    
    Args:
        ulan_id: Getty ULAN ID (e.g., "500123456" or full URI)
    
    Returns:
        Dictionary with name, biography, and full_data
    """
    # Extract ID from URI if needed
    if '/' in ulan_id:
        ulan_id = ulan_id.split('/')[-1]
    
    # Try JSON endpoint (may not always work)
    url = f"http://vocab.getty.edu/ulan/{ulan_id}.json"
    
    try:
        response = requests.get(url, timeout=10, headers=REQUESTS_HEADERS)
        response.raise_for_status()
        data = response.json()
        
        # Extract preferred name
        name = None
        if 'names' in data:
            for name_entry in data['names']:
                if name_entry.get('preferred', False):
                    name = name_entry.get('content', '')
                    break
        
        # Extract biographical information (simplified)
        biography = None
        if 'biographies' in data:
            bio_list = data['biographies']
            if bio_list:
                biography = bio_list[0].get('content', '')
        
        return {
            'name': name,
            'biography': biography,
            'full_data': data,
            'error': None
        }
    except Exception as e:
        # Getty JSON endpoint may not be available, return error
        return {
            'name': None,
            'biography': None,
            'full_data': None,
            'error': f'Getty ULAN JSON endpoint not available: {str(e)}'
        }


def fetch_loc(loc_id: str) -> Dict[str, Any]:
    """
    Fetch data from Library of Congress.
    
    Args:
        loc_id: LoC ID (e.g., "n123456" or full URI)
    
    Returns:
        Dictionary with name, biography, and full_data
    """
    # Extract ID from URI if needed
    if '/' in loc_id:
        loc_id = loc_id.split('/')[-1]
    
    # Try JSON-LD endpoint
    url = f"http://id.loc.gov/authorities/names/{loc_id}.jsonld"
    
    try:
        response = requests.get(url, timeout=10, headers=REQUESTS_HEADERS)
        response.raise_for_status()
        data = response.json()
        
        # Extract name (simplified - LoC JSON-LD can be complex)
        name = None
        if isinstance(data, list) and len(data) > 0:
            first_item = data[0]
            # Look for prefLabel or name
            name = first_item.get('http://www.w3.org/2004/02/skos/core#prefLabel', [{}])[0].get('@value', '')
            if not name:
                name = first_item.get('name', '')
        
        return {
            'name': name,
            'biography': None,  # LoC typically doesn't have biography in JSON-LD
            'full_data': data,
            'error': None
        }
    except Exception as e:
        return {
            'name': None,
            'biography': None,
            'full_data': None,
            'error': str(e)
        }


def extract_text_from_external_data(data: Dict[str, Any], source: str) -> str:
    """
    Convert external data JSON to plain text for embeddings.
    
    Args:
        data: The fetched data dictionary (from fetch_wikidata, fetch_getty_ulan, etc.)
        source: Source type ('wikidata', 'getty_ulan', 'loc', 'yale_person')
    
    Returns:
        Combined text string ready for embeddings
    """
    text_parts = []
    
    if source == 'wikidata':
        if data.get('description'):
            text_parts.append(data['description'])
        if data.get('biography'):
            text_parts.append(data['biography'])
    
    elif source == 'getty_ulan':
        if data.get('name'):
            text_parts.append(f"Name: {data['name']}")
        if data.get('biography'):
            text_parts.append(data['biography'])
    
    elif source == 'loc':
        if data.get('name'):
            text_parts.append(data['name'])
        if data.get('biography'):
            text_parts.append(data['biography'])
    
    elif source == 'yale_person':
        if data.get('name'):
            text_parts.append(f"Name: {data['name']}")
        if data.get('biography'):
            text_parts.append(data['biography'])
    
    return ' '.join(text_parts) if text_parts else ''

