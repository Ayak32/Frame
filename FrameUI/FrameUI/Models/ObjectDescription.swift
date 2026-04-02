//
//  ObjectDescription.swift
//  FrameUI
//
//  Created by Aya Kasim on 3/31/26.
//

import Foundation

struct ObjectDescriptionRequest: Encodable {
    let objectId: String
    let query: String
    let themes: String
}

struct ObjectDescriptionResponse: Decodable {
    let objectId: String
    let narrative: String
    let keyFacts: [String]
}
