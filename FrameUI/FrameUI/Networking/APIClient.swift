//
//  APIClient.swift
//  FrameUI
//
//  Centralized API client with global JSONEncoder/JSONDecoder
//

import Foundation

struct APIConfiguration {
    static let baseURL = URL(string: "http://127.0.0.1:8000")!
}

final class APIClient {
    static let shared = APIClient()
    private init() {}

    // Shared decoder using convertFromSnakeCase so backend snake_case keys map to camelCase properties
    static let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }()

    // Shared encoder using convertToSnakeCase so camelCase Swift properties map to backend snake_case keys
    static let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        return encoder
    }()

    func perform<T: Decodable>(_ request: URLRequest) async throws -> T {
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        return try APIClient.decoder.decode(T.self, from: data)
    }
}
