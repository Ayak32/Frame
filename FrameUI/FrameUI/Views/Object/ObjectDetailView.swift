//
//  ObjectDetailView.swift
//  FrameUI
//
//  Created by Aya Kasim on 3/31/26.
//

import SwiftUI
import UIKit

struct ObjectDetailView: View {
    @EnvironmentObject private var session: TourSession

    let objectId: String
    let title: String
    let themes: String
    let visitorQuery: String
    var context: RetrievedObjectContext? = nil

    @State private var enriched: ObjectDescriptionResponse?
    @State private var isLoadingEnriched = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                heroImage

                VStack(alignment: .leading, spacing: 20) {
                    Text(title)
                        .font(.title.weight(.bold))
                        .foregroundStyle(.primary)
                        .multilineTextAlignment(.leading)

                    metadataBlock

                    if isLoadingEnriched {
                        HStack(alignment: .center, spacing: 8) {
                            ProgressView()
                            Text("Loading more detail…")
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }
                        .padding(.vertical, 4)
                    }

                    if let enriched {
                        Divider()

                        sectionHeader("More about this work")
                        Text(enriched.narrative)
                            .font(.body)
                            .foregroundStyle(.primary)
                            .multilineTextAlignment(.leading)
                            .fixedSize(horizontal: false, vertical: true)

                        if !enriched.keyFacts.isEmpty {
                            VStack(alignment: .leading, spacing: 10) {
                                sectionHeader("Key facts", secondary: true)
                                ForEach(Array(enriched.keyFacts.enumerated()), id: \.offset) { _, fact in
                                    HStack(alignment: .top, spacing: 10) {
                                        Image(systemName: "circle.fill")
                                            .font(.system(size: 6))
                                            .foregroundStyle(.secondary)
                                            .padding(.top, 7)
                                        Text(fact)
                                            .font(.body)
                                            .foregroundStyle(.primary)
                                            .multilineTextAlignment(.leading)
                                            .fixedSize(horizontal: false, vertical: true)
                                    }
                                }
                            }
                            .padding(.top, 4)
                        }
                    }

                    objectFloorMapSection
                }
                .padding(.horizontal)
                .padding(.vertical, 20)
            }
        }
        .background(Color("LaunchScreenBackground"))
        .navigationTitle("Object")
        .navigationBarTitleDisplayMode(.inline)
        .task(id: objectId) {
            await withTaskGroup(of: Void.self) { group in
                group.addTask { await loadEnrichedDescription() }
                group.addTask { await session.loadFloorPlansIfNeeded() }
            }
        }
    }

    private var resolvedContext: RetrievedObjectContext? {
        context ?? session.context(for: objectId)
    }

    @ViewBuilder
    private var objectFloorMapSection: some View {
        if resolvedContext != nil {
            Divider()
                .padding(.top, 8)

            sectionHeader("Location on floor plan")

            if session.isLoadingFloorPlans {
                ProgressView()
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 12)
            } else if session.floorPlansLoadFailed {
                Text("Couldn’t load floor plans.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            } else if let ctx = resolvedContext,
                      let plan = FloorPlanPinHelper.matchingFloorPlan(for: ctx, in: session.floorPlans) {
                let pin = FloorPlanPinHelper.pin(for: ctx, plan: plan)
                let clusters = FloorPlanPinHelper.clusters(for: plan, contexts: [ctx])
                FloorPlanImageWithPinsView(plan: plan, clusters: clusters, interactivePins: false)
                if pin == nil {
                    Text("Pin position isn’t available for this work.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .padding(.top, 6)
                }
            } else if resolvedContext != nil {
                if session.floorPlans.isEmpty {
                    Text("No floor plans are available.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                } else {
                    Text("No floor plan matches this object’s floor.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }
        }
    }

    private func sectionHeader(_ text: String, secondary: Bool = false) -> some View {
        Text(text)
            .font(secondary ? .subheadline.weight(.semibold) : .headline)
            .foregroundStyle(secondary ? .secondary : .primary)
    }

    @ViewBuilder
    private var heroImage: some View {
        Group {
            if let urlString = resolvedContext?.object.imageUrl,
               let url = URL(string: urlString) {
                CachedRemoteImage(url: url, contentMode: .fit) {
                    ZStack {
                        Color.secondary.opacity(0.12)
                        ProgressView()
                    }
                }
            } else {
                heroPlaceholder
            }
        }
        .frame(maxWidth: .infinity)
        .background(Color("LaunchScreenBackground"))
    }

    private var heroPlaceholder: some View {
        ZStack {
            Color.secondary.opacity(0.12)
            Image(systemName: "photo")
                .font(.largeTitle)
                .foregroundStyle(.secondary)
        }
        .frame(height: 220)
    }

    @ViewBuilder
    private var metadataBlock: some View {
        let obj = resolvedContext?.object
        let detailLines = Self.objectDetailLines(from: obj)
        VStack(alignment: .leading, spacing: 8) {
            if let name = obj?.creatorName?.trimmingCharacters(in: .whitespacesAndNewlines), !name.isEmpty {
                Text(name)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }

            if !detailLines.isEmpty {
                Text(detailLines.joined(separator: " · "))
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.leading)
            }

            if let location = formattedLocation(context: resolvedContext) {
                Label(location, systemImage: "mappin.and.ellipse")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .labelStyle(.titleAndIcon)
            }

            if let desc = obj?.description?.trimmingCharacters(in: .whitespacesAndNewlines), !desc.isEmpty {
                Text(desc)
                    .font(.caption)
                    .foregroundStyle(.tertiary)
                    .multilineTextAlignment(.leading)
            }
        }
    }

    private static func objectDetailLines(from obj: TourObjectRecord?) -> [String] {
        guard let obj else { return [] }
        var lines: [String] = []
        if let period = obj.period?.trimmingCharacters(in: .whitespacesAndNewlines), !period.isEmpty {
            lines.append(period)
        }
        if let culture = obj.culture?.trimmingCharacters(in: .whitespacesAndNewlines), !culture.isEmpty {
            lines.append(culture)
        }
        if let mats = obj.materials, !mats.isEmpty {
            lines.append(mats.joined(separator: ", "))
        }
        return lines
    }

    private func formattedLocation(context: RetrievedObjectContext?) -> String? {
        guard let ctx = context else { return nil }
        if let loc = ctx.object.publicLocationString?.trimmingCharacters(in: .whitespacesAndNewlines), !loc.isEmpty {
            return Self.locationWithCaseAppended(loc, caseNumber: ctx.object.caseNumber)
        }
        var parts: [String] = []
        if let floor = ctx.object.floorLabel?.trimmingCharacters(in: .whitespacesAndNewlines), !floor.isEmpty {
            parts.append(floor)
        }
        if let g = ctx.object.galleryNumber?.trimmingCharacters(in: .whitespacesAndNewlines), !g.isEmpty {
            parts.append("Gallery \(g)")
        }
        if let caseNum = ctx.object.caseNumber {
            parts.append("Case \(caseNum)")
        }

        return parts.isEmpty ? nil : parts.joined(separator: " · ")
    }

    /// When the API sends a free-text location, still surface structured `case_number` if it is not already there.
    private static func locationWithCaseAppended(_ location: String, caseNumber: Int?) -> String {
        guard let cn = caseNumber else { return location }
        let needle = "Case \(cn)"
        if location.range(of: needle, options: .caseInsensitive) != nil { return location }
        return "\(location) · \(needle)"
    }

    private func loadEnrichedDescription() async {
        guard !objectId.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }

        isLoadingEnriched = true
        enriched = nil
        defer { isLoadingEnriched = false }
        do {
            enriched = try await session.fetchObjectDescriptionCached(
                objectId: objectId,
                visitorQuery: visitorQuery,
                themes: themes
            )
        } catch {
            enriched = nil
        }
    }
}

#Preview {
    NavigationStack {
        ObjectDetailView(
            objectId: "https://example.org/obj.json",
            title: "Sample",
            themes: "",
            visitorQuery: "impressionism",
            context: nil
        )
    }
    .environmentObject(TourSession())
}
