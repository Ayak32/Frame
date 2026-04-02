//
//  FloorPlan.swift
//  FrameUI
//
//  Created by Aya Kasim on 3/31/26.
//

import Foundation

struct FloorPlansResponse: Decodable {
    let floorPlans: [FloorPlan]
}

struct FloorPlan: Decodable {
    let ref: String
    let floorNumber: Int
    let imageUrl: String
    let widthPx: Int?
    let heightPx: Int?
}
