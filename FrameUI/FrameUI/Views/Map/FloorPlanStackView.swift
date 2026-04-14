//
//  FloorPlanStackView.swift
//  FrameUI
//

import SwiftUI

struct FloorPlanStackView: View {
    /// Tour /tour `retrieved_objects` used to plot `gallery_coordinates` pins.
    var tourObjects: [RetrievedObjectContext] = []

    @EnvironmentObject private var session: TourSession
    @State private var clusterPicker: FloorPinCluster?

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
                    LazyVStack(alignment: .center, spacing: 16) {
                        Text("Tap a gold star to see which tour stops are in that gallery.")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .fixedSize(horizontal: false, vertical: true)

                        ForEach(session.floorPlans.reversed(), id: \.ref) { plan in
                            FloorPlanImageWithPinsView(
                                plan: plan,
                                clusters: FloorPlanPinHelper.clusters(for: plan, contexts: tourObjects),
                                interactivePins: true,
                                onClusterTap: { cluster in
                                    clusterPicker = cluster
                                }
                            )
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
        .sheet(item: $clusterPicker) { cluster in
            NavigationStack {
                List {
                    Section {
                        ForEach(Array(cluster.contexts.enumerated()), id: \.offset) { _, ctx in
                            NavigationLink {
                                objectDetail(forContext: ctx)
                            } label: {
                                clusterRowLabel(ctx: ctx)
                            }
                            .listRowBackground(Color("LaunchScreenBackground"))
                            .listRowSeparator(.hidden)
                        }
                    } header: {
                        clusterSheetHeader(cluster: cluster)
                    }
                }
                .listStyle(.plain)
                .scrollContentBackground(.hidden)
                .navigationTitle("Tour stops")
                .navigationBarTitleDisplayMode(.inline)
                .toolbarBackground(Color("LaunchScreenBackground"), for: .navigationBar)
                .toolbarBackground(.visible, for: .navigationBar)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Close") { clusterPicker = nil }
                    }
                }
            }
            .background(Color("LaunchScreenBackground"))
            .environmentObject(session)
            .presentationDetents([.medium, .large])
            .presentationBackground(Color("LaunchScreenBackground"))
        }
        .task { await session.loadFloorPlansIfNeeded() }
        .background(Color("LaunchScreenBackground"))
    }

    @ViewBuilder
    private func clusterSheetHeader(cluster: FloorPinCluster) -> some View {
        let n = cluster.contexts.count
        Text(
            n == 1
                ? "This pin marks one stop on your tour."
                : "\(n) stops share this gallery location"
        )
        .font(.caption)
        .foregroundStyle(.secondary)
        .textCase(nil)
        .frame(maxWidth: .infinity, alignment: .center)
        .padding(.vertical, 4)
    }

    @ViewBuilder
    private func clusterRowLabel(ctx: RetrievedObjectContext) -> some View {
        let rawTitle = ctx.object.title?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        let rowTitle = rawTitle.isEmpty ? "Untitled" : rawTitle
        VStack(alignment: .leading, spacing: 4) {
            Text(rowTitle)
                .font(.headline)
            if let creator = ctx.object.creatorName?.trimmingCharacters(in: .whitespacesAndNewlines), !creator.isEmpty {
                Text(creator)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
        }
    }

    @ViewBuilder
    private func objectDetail(forContext ctx: RetrievedObjectContext?, objectId: String? = nil) -> some View {
        let oid = objectId ?? ctx?.object.id ?? ""
        let rawTitle = ctx?.object.title?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        let title = rawTitle.isEmpty ? "Untitled" : rawTitle
        ObjectDetailView(
            objectId: oid,
            title: title,
            themes: session.lastResponse?.themes ?? "",
            visitorQuery: session.lastVisitorQuery,
            context: ctx
        )
        .environmentObject(session)
    }
}

#Preview {
    NavigationStack {
        FloorPlanStackView(tourObjects: [])
    }
    .environmentObject(TourSession())
}
