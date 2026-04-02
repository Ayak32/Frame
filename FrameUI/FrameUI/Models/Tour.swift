////
////  Tour.swift
////  FrameUI
////
////  Created by Aya Kasim on 3/31/26.
////  For /tour endpoint
//

import Foundation

// MARK: - POST /tour response

struct TourResponse: Decodable {
    let tour: [TourStop]
    let themes: String
    let retrievedObjects: [RetrievedObjectContext]
    // CodingKeys synthesized: works with APIClient.decoder's convertFromSnakeCase
    // (e.g. retrieved_objects → retrievedObjects). Do not use raw values like
    // retrieved_objects here — that conflicts with convertFromSnakeCase.
}

/// LLM-produced stops (see TOUR_SYSTEM_PROMPT).
struct TourStop: Decodable {
    let objectId: String
    let title: String
    let narrative: String
    let order: Int
    let galleryNumber: String?

    enum CodingKeys: String, CodingKey {
        case objectId, title, narrative, order, galleryNumber
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        objectId = try c.decode(String.self, forKey: .objectId)
        title = try c.decode(String.self, forKey: .title)
        narrative = try c.decode(String.self, forKey: .narrative)
        order = try c.decodeLosslessInteger(forKey: .order)
        galleryNumber = try c.decodeIfPresent(String.self, forKey: .galleryNumber)
    }
}

// MARK: - Retrieved context (from `_enrich_object_row` + retrieval scores)

struct RetrievedObjectContext: Decodable {
    let object: TourObjectRecord
    let galleryCoordinates: GalleryCoordinates?
    let floorPlanImageURL: String?
    let artist: TourArtist?
    let visualItems: [VisualItemSnippet]
    let retrieval: RetrievalScores

    enum CodingKeys: String, CodingKey {
        case object, artist, retrieval
        case galleryCoordinates
        /// JSON `floor_plan_image_url` → `floorPlanImageUrl` under convertFromSnakeCase (not …URL).
        case floorPlanImageURL = "floorPlanImageUrl"
        case visualItems
    }
}

struct TourObjectRecord: Decodable {
    let id: String?
    let title: String?
    let creatorName: String?
    let creatorId: String?
    let classification: [String]?
    let culture: String?
    let period: String?
    let materials: [String]?
    /// Maps from DB `dimensions_text` in the API.
    let description: String?
    let audioGuideTranscript: String?
    let galleryNumber: String?
    let locationString: String?
    let galleryBaseNumber: Int?
    let caseNumber: Int?
    let floorNumber: Int?
    let floorLabel: String?

    enum CodingKeys: String, CodingKey {
        case id, title, culture, period, materials, description, classification
        case creatorName, creatorId
        case audioGuideTranscript
        case galleryNumber, locationString, galleryBaseNumber, caseNumber, floorNumber, floorLabel
    }
}

/// `galleries.coordinates` JSONB — extend if you add keys.
struct GalleryCoordinates: Decodable {
    let nx: Double?
    let ny: Double?
    let x: Double?
    let y: Double?
    let floorNumber: Int?

    enum CodingKeys: String, CodingKey {
        case nx, ny, x, y, floorNumber
    }
}

struct TourArtist: Decodable {
    let name: String?
    let biographyText: String?

    enum CodingKeys: String, CodingKey {
        case name, biographyText
    }
}

struct VisualItemSnippet: Decodable {
    let id: String?
    let styleClassifications: [String]?
    let depictedPlaces: [String]?
    let subjectMatter: [String]?
    let extractedText: String?

    enum CodingKeys: String, CodingKey {
        case id, styleClassifications, depictedPlaces, subjectMatter, extractedText
    }
}

struct RetrievalScores: Decodable {
    let distance: Double?
    let similarity: Double?
}

// MARK: - Helpers

private extension KeyedDecodingContainer {
    /// Accepts JSON numbers as Int (some encoders use Double for small integers).
    func decodeLosslessInteger(forKey key: Key) throws -> Int {
        if let i = try? decode(Int.self, forKey: key) { return i }
        if let d = try? decode(Double.self, forKey: key) { return Int(d) }
        let s = try decode(String.self, forKey: key)
        guard let i = Int(s) else {
            throw DecodingError.dataCorruptedError(forKey: key, in: self, debugDescription: "Not an integer")
        }
        return i
    }
}











//import Foundation
//
struct TourRequest: Encodable {
    let query: String
    let timeLimit: Int
    var floorNumber: Int? = nil
    var galleryNumber: String? = nil
}
//
//struct TourResponse: Decodable {
//    let tour: [TourStop]
//    let themes: String
//    let retrievedObjects: [RetrievedObject]
//    
//    private enum CodingKeys: String, CodingKey {
//        case tour
//        case themes
//        case retrievedObjects = "retrieved_objects" // adjust if backend uses snake_case
//    }
//}
//
//struct TourStop: Decodable {
//    let objectId: String
//    let title: String?
//    let narrative: String?
//    let order: Int?
//    let galleryNumber: String?
//    
//    private enum CodingKeys: String, CodingKey {
//            case objectId = "object_id"
//            case title
//            case narrative
//            case order
//            case galleryNumber = "gallery_number"
//        }
//}
//
////struct RetrievedObject: Decodable {
////    let objectId: String
////    let title: String?
////    let galleryNumber: String?
////}
//
//struct RetrievedObject: Decodable {
//    let object: RetrievedObject.ObjectPayload
//    let artist: RetrievedObject.ArtistPayload?
//    let visualItems: [RetrievedObject.VisualItem]
//    let galleryCoordinates: RetrievedObject.GalleryCoordinates?
//    let floorPlanImageUrl: URL?
//    let retrieval: RetrievedObject.Retrieval
//
//    private enum CodingKeys: String, CodingKey {
//        case object
//        case artist
//        case visualItems = "visual_items"
//        case galleryCoordinates = "gallery_coordinates"
//        case floorPlanImageUrl = "floor_plan_image_url"
//        case retrieval
//    }
//
//    struct ObjectPayload: Decodable {
//        let id: String
//        let title: String?
//        let creatorName: String?
//        let creatorId: String?
//        let classification: String?
//        let culture: String?
//        let period: String?
//        let materials: String?
//        let description: String?
//        let audioGuideTranscript: String?
//        let linkedArtJson: String?
//        let galleryNumber: String?
//        let locationString: String?
//        let galleryBaseNumber: String?
//        let caseNumber: String?
//        let floorNumber: Int?
//        let floorLabel: String?
//
//        private enum CodingKeys: String, CodingKey {
//            case id
//            case title
//            case creatorName = "creator_name"
//            case creatorId = "creator_id"
//            case classification
//            case culture
//            case period
//            case materials
//            case description
//            case audioGuideTranscript = "audio_guide_transcript"
//            case linkedArtJson = "linked_art_json"
//            case galleryNumber = "gallery_number"
//            case locationString = "location_string"
//            case galleryBaseNumber = "gallery_base_number"
//            case caseNumber = "case_number"
//            case floorNumber = "floor_number"
//            case floorLabel = "floor_label"
//        }
//    }
//
//    struct ArtistPayload: Decodable {
//        let name: String?
//        let biographyText: String?
//
//        private enum CodingKeys: String, CodingKey {
//            case name
//            case biographyText = "biography_text"
//        }
//    }
//
//    struct VisualItem: Decodable {
//        let id: String
//        let styleClassifications: [String]?
//        let depictedPlaces: [String]?
//        let subjectMatter: [String]?
//        let extractedText: String?
//
//        private enum CodingKeys: String, CodingKey {
//            case id
//            case styleClassifications = "style_classifications"
//            case depictedPlaces = "depicted_places"
//            case subjectMatter = "subject_matter"
//            case extractedText = "extracted_text"
//        }
//    }
//
//    struct GalleryCoordinates: Decodable {
//        // Adjust these to match the actual coordinate payload from your backend
//        let x: Double?
//        let y: Double?
//        let z: Double?
//    }
//
//    struct Retrieval: Decodable {
//        let distance: Double?
//        let similarity: Double?
//    }
//}
