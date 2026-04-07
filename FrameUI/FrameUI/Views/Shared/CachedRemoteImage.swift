//
//  CachedRemoteImage.swift
//  FrameUI
//

import Foundation
import SwiftUI
import UIKit

actor RemoteImageCache {
    static let shared = RemoteImageCache()

    private let cache = NSCache<NSURL, UIImage>()
    private var inFlight: [NSURL: Task<UIImage, Error>] = [:]

    func image(for url: URL) async throws -> UIImage {
        let key = url as NSURL

        if let cached = cache.object(forKey: key) {
            return cached
        }

        if let task = inFlight[key] {
            return try await task.value
        }

        let task = Task<UIImage, Error> {
            let (data, response) = try await URLSession.shared.data(from: url)
            if let http = response as? HTTPURLResponse, !(200...299).contains(http.statusCode) {
                throw URLError(.badServerResponse)
            }
            guard let image = UIImage(data: data) else {
                throw URLError(.cannotDecodeContentData)
            }
            return image
        }

        inFlight[key] = task

        do {
            let image = try await task.value
            cache.setObject(image, forKey: key)
            inFlight[key] = nil
            return image
        } catch {
            inFlight[key] = nil
            throw error
        }
    }
}

struct CachedRemoteImage<Placeholder: View>: View {
    let url: URL
    let contentMode: ContentMode
    @ViewBuilder var placeholder: () -> Placeholder

    @State private var uiImage: UIImage?
    @State private var didFail = false

    var body: some View {
        Group {
            if let uiImage {
                Image(uiImage: uiImage)
                    .resizable()
                    .aspectRatio(contentMode: contentMode)
            } else if didFail {
                placeholder()
            } else {
                placeholder()
                    .task(id: url) { await load() }
            }
        }
    }

    private func load() async {
        do {
            let img = try await RemoteImageCache.shared.image(for: url)
            self.uiImage = img
        } catch {
            didFail = true
        }
    }
}

