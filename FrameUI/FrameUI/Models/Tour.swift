////
////  Tour.swift
////  FrameUI
////
////  Created by Aya Kasim on 3/31/26.
////  For /tour endpoint
//

import Foundation

struct TourRequest: Encodable {
    let query: String
    let timeLimit: Int
    var floorNumber: Int? = nil
    var galleryNumber: String? = nil
}


struct TourResponse: Decodable {
    let tour: [TourStop]
    let themes: String
    let retrievedObjects: [RetrievedObjectContext]
}



/// LLM-produced stops (see TOUR_SYSTEM_PROMPT).
struct TourStop: Decodable {
    let objectId: String
    let title: String
//    let narrative: String
    let order: Int
    let galleryNumber: String?

    enum CodingKeys: String, CodingKey {
        case objectId, title, order, galleryNumber
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        objectId = try c.decode(String.self, forKey: .objectId)
        title = try c.decode(String.self, forKey: .title)
//        narrative = try c.decode(String.self, forKey: .narrative)
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
    let description: String?
    let audioGuideTranscript: String?
    let imageUrl: String?
    let galleryNumber: String?
    let publicLocationString: String?
    let galleryBaseNumber: Int?
    let caseNumber: Int?
    let floorNumber: Int?
    let floorLabel: String?

    enum CodingKeys: String, CodingKey {
        case id, title, culture, period, materials, description, classification
        case creatorName, creatorId
        case audioGuideTranscript
        case imageUrl
        case galleryNumber, publicLocationString, galleryBaseNumber, caseNumber, floorNumber, floorLabel
    }
}

/// `galleries.coordinates` JSONB — extend if you add keys.
struct GalleryCoordinates: Decodable {
    let nx: Double?
    let ny: Double?
    let x: Double?
    let y: Double?
    let floorNumber: Int?
    /// Matches `FloorPlan.ref` when a floor has multiple plan images.
    let ref: String?

    enum CodingKeys: String, CodingKey {
        case nx, ny, x, y, floorNumber, ref
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

