//
//  FrameAPI.swift
//  FrameUI
//
//  Created by Aya Kasim on 3/31/26.
//

import Foundation


func fetchTour(request: TourRequest) async throws -> TourResponse {
    var urlRequest = URLRequest(url: APIConfiguration.baseURL.appendingPathComponent("/tour"))
    
    urlRequest.httpMethod = "POST"
    urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")

    urlRequest.httpBody = try APIClient.encoder.encode(request)
    
    return try await
    APIClient.shared.perform(urlRequest)

}

func fetchObjectDescription(request: ObjectDescriptionRequest) async throws -> ObjectDescriptionResponse {
    var urlRequest = URLRequest(url: APIConfiguration.baseURL.appendingPathComponent("/objects/description"))
    
    urlRequest.httpMethod = "POST"
    urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")

    urlRequest.httpBody = try APIClient.encoder.encode(request)
    
    return try await
    APIClient.shared.perform(urlRequest)

}


func fetchFloorPlans() async throws -> FloorPlansResponse {
    var urlRequest = URLRequest(url: APIConfiguration.baseURL.appendingPathComponent("/floor-plans"))
    
    urlRequest.httpMethod = "GET"
    urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
    
    return try await
    APIClient.shared.perform(urlRequest)

}

func healthCheck() async throws -> HealthCheckResponse {
    var urlRequest = URLRequest(url: APIConfiguration.baseURL.appendingPathComponent("/health"))
                             
    urlRequest.httpMethod = "GET"
    return try await APIClient.shared.perform(urlRequest)
}
