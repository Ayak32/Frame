//
//  ObjectDetailView.swift
//  FrameUI
//
//  Created by Aya Kasim on 3/31/26.
//

import SwiftUI
import UIKit

struct ObjectDetailView: View {
    let objectId: String
    let title: String
    let narrative: String
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

                    if !narrative.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                        sectionHeader("On your tour")
                        Text(narrative)
                            .font(.body)
                            .foregroundStyle(.primary)
                            .multilineTextAlignment(.leading)
                            .fixedSize(horizontal: false, vertical: true)
                    }

                    if isLoadingEnriched {
                        HStack(spacing: 8) {
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
                }
                .padding(.horizontal)
                .padding(.vertical, 20)
            }
        }
        .background(Color(uiColor: UIColor.systemGroupedBackground))
        .navigationTitle("Object")
        .navigationBarTitleDisplayMode(.inline)
        .task(id: objectId) {
            await loadEnrichedDescription()
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
            if let urlString = context?.object.imageUrl,
               let url = URL(string: urlString) {
                AsyncImage(url: url) { phase in
                    switch phase {
                    case .success(let image):
                        image
                            .resizable()
                            .scaledToFit()
                    case .failure:
                        heroPlaceholder
                    case .empty:
                        ZStack {
                            Color.secondary.opacity(0.12)
                            ProgressView()
                        }
                    @unknown default:
                        heroPlaceholder
                    }
                }
            } else {
                heroPlaceholder
            }
        }
        .frame(maxWidth: .infinity)
        .background(Color.secondary.opacity(0.08))
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
        let obj = context?.object
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

            if let location = formattedLocation(context: context) {
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
        if let loc = ctx.object.locationString?.trimmingCharacters(in: .whitespacesAndNewlines), !loc.isEmpty {
            return loc
        }
        var parts: [String] = []
        if let floor = ctx.object.floorLabel?.trimmingCharacters(in: .whitespacesAndNewlines), !floor.isEmpty {
            parts.append(floor)
        }
        if let g = ctx.object.galleryNumber?.trimmingCharacters(in: .whitespacesAndNewlines), !g.isEmpty {
            parts.append("Gallery \(g)")
        }
        return parts.isEmpty ? nil : parts.joined(separator: " · ")
    }

    private func loadEnrichedDescription() async {
        guard !objectId.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        isLoadingEnriched = true
        enriched = nil
        defer { isLoadingEnriched = false }
        do {
            let request = ObjectDescriptionRequest(
                objectId: objectId,
                query: visitorQuery,
                themes: themes
            )
            enriched = try await fetchObjectDescription(request: request)
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
            narrative: "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore.",
            themes: "",
            visitorQuery: "impressionism",
            context: nil
        )
    }
}
