//
//  TourSession.swift
//  FrameUI
//
//  Created by Aya Kasim on 3/31/26.
//

import Foundation
import Combine

@MainActor
final class TourSession: ObservableObject {
   @Published var lastResponse: TourResponse?
   @Published var isLoading = false
   @Published var errorMessage: String?
   /// useful for /objects/description
   @Published var lastVisitorQuery: String = ""

   func context(for objectId: String) -> RetrievedObjectContext? {
       lastResponse?.retrievedObjects.first { $0.object.id == objectId }
   }

   func loadTour(query: String, timeLimitMinutes: Int, floorNumber: Int?, galleryNumber: String?) async {
       errorMessage = nil
       let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
       guard !trimmed.isEmpty else {
           errorMessage = "Enter what you’d like to explore."
           return
       }

       let minutes = max(6, min(180, timeLimitMinutes))
       var request = TourRequest(query: trimmed, timeLimit: minutes)
       request.floorNumber = floorNumber
       request.galleryNumber = normalizedOptionalString(galleryNumber)

       isLoading = true
       defer { isLoading = false }

       do {
           lastVisitorQuery = trimmed
           lastResponse = try await fetchTour(request: request)
       } catch {
           lastResponse = nil
           errorMessage = error.localizedDescription
       }
   }

   private func normalizedOptionalString(_ value: String?) -> String? {
       guard let value = value?.trimmingCharacters(in: .whitespacesAndNewlines), !value.isEmpty else {
           return nil
       }
       return value
   }
}


