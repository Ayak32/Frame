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
   // Cached across map sheet presentations so we don't refetch every time.
   @Published var floorPlans: [FloorPlan] = []
   @Published var isLoadingFloorPlans = false
   @Published var floorPlansLoadFailed = false

   private struct ObjectDescriptionCacheKey: Hashable {
       let objectId: String
       let visitorQuery: String
       let themes: String
   }

   private var objectDescriptionCache: [ObjectDescriptionCacheKey: ObjectDescriptionResponse] = [:]
   private var objectDescriptionInFlight: [ObjectDescriptionCacheKey: Task<ObjectDescriptionResponse, Error>] = [:]

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

   func cachedObjectDescription(
       objectId: String,
       visitorQuery: String,
       themes: String
   ) -> ObjectDescriptionResponse? {
       let key = ObjectDescriptionCacheKey(
           objectId: objectId,
           visitorQuery: visitorQuery,
           themes: themes
       )
       return objectDescriptionCache[key]
   }

   func fetchObjectDescriptionCached(
       objectId: String,
       visitorQuery: String,
       themes: String
   ) async throws -> ObjectDescriptionResponse {
       let oid = objectId.trimmingCharacters(in: .whitespacesAndNewlines)
       let q = visitorQuery.trimmingCharacters(in: .whitespacesAndNewlines)
       let t = themes.trimmingCharacters(in: .whitespacesAndNewlines)

       let key = ObjectDescriptionCacheKey(objectId: oid, visitorQuery: q, themes: t)

       if let cached = objectDescriptionCache[key] {
           return cached
       }

       if let task = objectDescriptionInFlight[key] {
           return try await task.value
       }

       let task = Task<ObjectDescriptionResponse, Error> {
           let request = ObjectDescriptionRequest(objectId: oid, query: q, themes: t)
           return try await fetchObjectDescription(request: request)
       }
       objectDescriptionInFlight[key] = task

       do {
           let res = try await task.value
           objectDescriptionCache[key] = res
           objectDescriptionInFlight[key] = nil
           return res
       } catch {
           objectDescriptionInFlight[key] = nil
           throw error
       }
   }

   func loadFloorPlansIfNeeded() async {
       guard floorPlans.isEmpty else { return }
       await loadFloorPlans(force: false)
   }

   func loadFloorPlans(force: Bool) async {
       if isLoadingFloorPlans { return }
       if !force, !floorPlans.isEmpty { return }

       isLoadingFloorPlans = true
       floorPlansLoadFailed = false
       defer { isLoadingFloorPlans = false }

       do {
           let res = try await fetchFloorPlans()
           floorPlans = res.floorPlans.sorted {
               $0.floorNumber != $1.floorNumber
                   ? $0.floorNumber < $1.floorNumber
                   : $0.ref < $1.ref
           }
       } catch {
           floorPlans = []
           floorPlansLoadFailed = true
       }
   }

   private func normalizedOptionalString(_ value: String?) -> String? {
       guard let value = value?.trimmingCharacters(in: .whitespacesAndNewlines), !value.isEmpty else {
           return nil
       }
       return value
   }
}


