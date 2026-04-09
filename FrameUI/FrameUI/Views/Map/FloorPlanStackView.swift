//
//  FloorPlanStackView.swift
//  FrameUI
//

import SwiftUI

struct FloorPlanStackView: View {
    /// Tour /tour `retrieved_objects` used to plot `gallery_coordinates` pins.
    var tourObjects: [RetrievedObjectContext] = []

    @EnvironmentObject private var session: TourSession

    var body: some View {
        Group {
            if session.isLoadingFloorPlans {
                ProgressView()
            } else if session.floorPlansLoadFailed {
                ContentUnavailableView(
                    "Couldn’t load floor plans",
                    systemImage: "map",
                    description: Text("Check your connection and try opening the map again.")
                )
            } else if session.floorPlans.isEmpty {
                ContentUnavailableView("No floor plans", systemImage: "map")
            } else {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 0) {
                        ForEach(session.floorPlans.reversed(), id: \.ref) { plan in
                            VStack(alignment: .leading, spacing: 0) {
                                FloorPlanImageWithPinsView(
                                    plan: plan,
                                    pins: FloorPlanPinHelper.pins(for: plan, contexts: tourObjects)
                                )
                            }
                        }
                    }
                    .padding()
                }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color("LaunchScreenBackground"))
        .navigationTitle("Floor plan")
        .navigationBarTitleDisplayMode(.inline)
        .task { await session.loadFloorPlansIfNeeded() }
    }
}

#Preview {
    NavigationStack {
        FloorPlanStackView(tourObjects: [])
    }
    .environmentObject(TourSession())
}
