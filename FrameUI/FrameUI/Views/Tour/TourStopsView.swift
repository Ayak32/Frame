//
//  TourStopsView.swift
//  FrameUI
//
//  Created by Aya Kasim on 4/2/26.
//

import SwiftUI

struct TourStopsView: View {
    @EnvironmentObject private var session: TourSession
    @State private var showMap = false
    @State private var selectedStop: SelectedStop?

    private struct SelectedStop: Identifiable, Hashable {
        let id: String
        let title: String
        let themes: String
        let visitorQuery: String
        let context: RetrievedObjectContext?

        static func == (lhs: SelectedStop, rhs: SelectedStop) -> Bool {
            lhs.id == rhs.id
        }

        func hash(into hasher: inout Hasher) {
            hasher.combine(id)
        }
    }


    var body: some View {
        Group {             
            if let response = session.lastResponse {
                List {
                    ForEach(sortedStops(from: response), id: \.objectId) { stop in
                        let context = session.context(for: stop.objectId)
                        Button {
                            selectedStop = SelectedStop(
                                id: stop.objectId,
                                title: displayTitle(stop: stop, context: context),
                                themes: response.themes,
                                visitorQuery: session.lastVisitorQuery,
                                context: context
                            )
                        } label: {
                            TourStopCardRow(stop: stop, context: context)
                        }
                        .buttonStyle(.plain)
                        .contentShape(Rectangle())
                        // Default UITableViewCell background is white; paint the full row (edges + gaps) cream.
                        .listRowBackground(Color("LaunchScreenBackground"))
                        .listRowSeparator(.hidden)
                    }
                }
                .listStyle(.plain)
                .listRowSpacing(0)
                .scrollContentBackground(.hidden)
                .background(Color("LaunchScreenBackground"))
                .navigationBarTitleDisplayMode(.inline)
                .toolbarColorScheme(.light, for: .navigationBar)
                .toolbarBackground(Color("LaunchScreenBackground"), for: .navigationBar)
                .toolbarBackground(.visible, for: .navigationBar)
                .navigationDestination(item: $selectedStop) { selected in
                    ObjectDetailView(
                        objectId: selected.id,
                        title: selected.title,
                        themes: selected.themes,
                        visitorQuery: selected.visitorQuery,
                        context: selected.context
                    )
                    .environmentObject(session)
                }
                .toolbar {
                    ToolbarItem(placement: .principal) {
                        Text("Your Tour")
                            .font(.custom("American Typewriter", size: 28))
                            // Fixed color: `.primary` tracks bar material and shifts when the list scrolls (scroll-edge appearance).
                            .foregroundStyle(Color(white: 0.15))
                    }
                    ToolbarItem(placement: .topBarTrailing) {
                        Button {
                            showMap = true
                        } label: {
                            Image(systemName: "map")
                        }
                        .foregroundStyle(Color(white: 0.15))
                        .accessibilityLabel("Floor map")
                    }
                }
                .sheet(isPresented: $showMap) {
                    NavigationStack {
                        FloorPlanStackView(tourObjects: response.retrievedObjects)
                            .environmentObject(session)
                            .toolbar {
                                ToolbarItem(placement: .cancellationAction) {
                                    Button("Done") { showMap = false }
                                }
                            }
                    }
                }
            } else {
                ContentUnavailableView(
                    "No tour loaded yet.",
                    systemImage: "figure.walk",
                    description: Text("Start a tour to see your stops.")
                )
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color("LaunchScreenBackground"))
            }
        }.background(Color("LaunchScreenBackground"))
    }
}
private func sortedStops(from response: TourResponse) -> [TourStop] {
    // Sort by retrieval relevance order (most relevant first)
    let ranks: [String: Int] = Dictionary(uniqueKeysWithValues:
        response.retrievedObjects.enumerated().compactMap { (offset, ctx) in
            guard let id = ctx.object.id else { return nil }
            return (id, offset)
        }
    )
    return response.tour.sorted { a, b in
        let ra = ranks[a.objectId] ?? a.order
        let rb = ranks[b.objectId] ?? b.order
        return ra < rb
    }
}

private struct TourStopCardRow: View {
    let stop: TourStop
    let context: RetrievedObjectContext?
    var body: some View {
        VStack() {
            thumbnail
            VStack(alignment: .leading, spacing: 4) {
                Text(displayTitle(stop: stop, context: context))
                    .font(.headline)
                    .foregroundStyle(.primary)
                    .multilineTextAlignment(.leading)
                Text(creatorSubtitle(stop: stop, context: context))
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.leading)
                Text(locationSubtitle(stop: stop, context: context))
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.leading)
            }
            Spacer(minLength: 0)
        }
        .padding(.vertical, 4)
        .background(Color("LaunchScreenBackground"))
    }
    @ViewBuilder
    private var thumbnail: some View {
        Group {
            if let s = context?.object.imageUrl,
               let url = URL(string: s) {
                CachedRemoteImage(url: url, contentMode: .fill) {
                    placeholderIcon
                }
            } else {
                placeholderIcon
            }
        }
        .frame(maxWidth: .infinity)
        .clipped()
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }

    private static let thumbnailSize: CGFloat = 88

    private var placeholderIcon: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .fill(Color.secondary.opacity(0.15))
            Image(systemName: "photo")
                .font(.title2)
                .foregroundStyle(.secondary)
        }
        .frame(width: Self.thumbnailSize, height: Self.thumbnailSize)
    }
}
// - Formatting helpers
private func displayTitle(stop: TourStop, context: RetrievedObjectContext?) -> String {
    let t = stop.title.trimmingCharacters(in: .whitespacesAndNewlines)
    if !t.isEmpty { return t }
    if let o = context?.object.title?.trimmingCharacters(in: .whitespacesAndNewlines), !o.isEmpty {
        return o
    }
    return "Untitled"
}
private func creatorSubtitle(stop: TourStop, context: RetrievedObjectContext?) -> String {
    if let creator =
        context?.object.creatorName?
        .trimmingCharacters(in: .whitespacesAndNewlines),
       !creator.isEmpty {
        return creator
    }
    return "Unknown Creator"
}
private func locationSubtitle(stop: TourStop, context: RetrievedObjectContext?) -> String {
    if let loc = context?.object.publicLocationString?.trimmingCharacters(in: .whitespacesAndNewlines),
       !loc.isEmpty {
        return loc
    }
    var parts: [String] = []
    if let floor = context?.object.floorLabel?.trimmingCharacters(in: .whitespacesAndNewlines), !floor.isEmpty {
        parts.append(floor)
    }
    let gallery = (stop.galleryNumber ?? context?.object.galleryNumber)?
        .trimmingCharacters(in: .whitespacesAndNewlines)
    if let gallery, !gallery.isEmpty {
        parts.append("Gallery \(gallery)")
    }
    return parts.isEmpty ? "Location not listed" : parts.joined(separator: " · ")
}
#Preview {
    NavigationStack {
        TourStopsView()
            .environmentObject(TourSession())
    }
}
