//
//  TourRequestView.swift
//  FrameUI
//
//  Created by Aya Kasim on 3/31/26.
//

import SwiftUI

struct BackendTestView: View {
    @State private var result: String = "Tap to test"
    @State private var isLoading = false

    var body: some View {
        VStack(spacing: 12) {
            Text(result)
                .font(.footnote)
                .multilineTextAlignment(.center)

            Button(isLoading ? "Testing..." : "Test Backend") {
                Task {
                    isLoading = true
                    defer { isLoading = false }
                    do {
                        // Example: call fetchFloorPlans
                        let request = ObjectDescriptionRequest(objectId: "https://media.art.yale.edu/content/lux/obj/69.json", query: "a tour about american revolution", themes: "art in war")
                        let response: ObjectDescriptionResponse = try await fetchObjectDescription(request: request)
                        result = "Success: \(response)"
                    } catch {
                        result = "Error: \(error.localizedDescription)"
                    }
                }
            }
            .disabled(isLoading)
        }
        .padding()
    }
}
