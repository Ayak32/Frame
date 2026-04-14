//
//  FloorPlanImageWithPins.swift
//  FrameUI
//
//  Shared floor plan image + normalized pin overlay (used by FloorPlanStackView and ObjectDetailView).
//

import SwiftUI

struct FloorMapPin: Identifiable {
    let id: String
    let nx: CGFloat
    let ny: CGFloat
}

/// One or more tour objects sharing (approximately) the same floor-plan coordinates.
struct FloorPinCluster: Identifiable {
    let id: String
    let nx: CGFloat
    let ny: CGFloat
    let contexts: [RetrievedObjectContext]
}

enum FloorPlanPinHelper {
    /// Normalized 0…1 in image space (top-left origin), matching `FloorPlanStackView` behavior.
    static func normalizedXY(coords: GalleryCoordinates, plan: FloorPlan) -> (CGFloat, CGFloat)? {
        if let nx = coords.nx, let ny = coords.ny {
            let x = nx > 1.0 ? nx / 100.0 : nx
            let y = ny > 1.0 ? ny / 100.0 : ny
            if (0...1).contains(x), (0...1).contains(y) {
                return (CGFloat(x), CGFloat(y))
            }
        }
        if let w = plan.widthPx, let h = plan.heightPx, w > 0, h > 0,
           let px = coords.x, let py = coords.y {
            return (CGFloat(px) / CGFloat(w), CGFloat(py) / CGFloat(h))
        }
        return nil
    }

    static func pin(for context: RetrievedObjectContext, plan: FloorPlan) -> FloorMapPin? {
        guard let oid = context.object.id?.trimmingCharacters(in: .whitespacesAndNewlines), !oid.isEmpty else {
            return nil
        }
        guard let coords = context.galleryCoordinates else { return nil }

        let floorObj = context.object.floorNumber
        let floorCoord = coords.floorNumber
        let floor = floorObj ?? floorCoord
        guard let floor, floor == plan.floorNumber else { return nil }

        if let r = coords.ref?.trimmingCharacters(in: .whitespacesAndNewlines), !r.isEmpty, r != plan.ref {
            return nil
        }

        guard let (nx, ny) = normalizedXY(coords: coords, plan: plan) else { return nil }
        return FloorMapPin(id: oid, nx: nx, ny: ny)
    }

    static func pins(for plan: FloorPlan, contexts: [RetrievedObjectContext]) -> [FloorMapPin] {
        contexts.compactMap { pin(for: $0, plan: plan) }
    }

    /// Groups objects that map to the same pin position on this floor plan (collision handling).
    static func clusters(for plan: FloorPlan, contexts: [RetrievedObjectContext]) -> [FloorPinCluster] {
        struct Placement {
            let nx: CGFloat
            let ny: CGFloat
            let context: RetrievedObjectContext
            let sourceIndex: Int
        }
        let placements: [Placement] = contexts.enumerated().compactMap { index, ctx in
            guard let p = pin(for: ctx, plan: plan) else { return nil }
            return Placement(nx: p.nx, ny: p.ny, context: ctx, sourceIndex: index)
        }
        var buckets: [String: [Placement]] = [:]
        for pl in placements {
            let key = pinCollisionKey(nx: pl.nx, ny: pl.ny)
            buckets[key, default: []].append(pl)
        }
        return buckets.values.compactMap { group -> FloorPinCluster? in
            guard let first = group.min(by: { $0.sourceIndex < $1.sourceIndex }) else { return nil }
            let ordered = group.sorted { $0.sourceIndex < $1.sourceIndex }.map(\.context)
            let stableId = ordered.compactMap { $0.object.id }.sorted().joined(separator: "|")
            let id = stableId.isEmpty ? "\(first.nx)_\(first.ny)_\(UUID().uuidString)" : stableId
            return FloorPinCluster(id: id, nx: first.nx, ny: first.ny, contexts: ordered)
        }
        .sorted { a, b in
            if a.ny != b.ny { return a.ny < b.ny }
            return a.nx < b.nx
        }
    }

    private static func pinCollisionKey(nx: CGFloat, ny: CGFloat) -> String {
        let qx = Int((Double(nx) * 10_000).rounded())
        let qy = Int((Double(ny) * 10_000).rounded())
        return "\(qx)_\(qy)"
    }

    /// Picks the `FloorPlan` row for this object’s floor (and optional `coords.ref`).
    static func matchingFloorPlan(for context: RetrievedObjectContext?, in floorPlans: [FloorPlan]) -> FloorPlan? {
        guard let context else { return nil }
        let floorObj = context.object.floorNumber
        let floorCoord = context.galleryCoordinates?.floorNumber
        guard let floor = floorObj ?? floorCoord else { return nil }

        let candidates = floorPlans.filter { $0.floorNumber == floor }
        guard !candidates.isEmpty else { return nil }

        if let ref = context.galleryCoordinates?.ref?.trimmingCharacters(in: .whitespacesAndNewlines), !ref.isEmpty {
            return candidates.first(where: { $0.ref == ref }) ?? candidates.first
        }
        return candidates.first
    }
}

struct FloorPlanImageWithPinsView: View {
    let plan: FloorPlan
    let clusters: [FloorPinCluster]
    /// When false, pins are display-only (e.g. embedded map on object detail).
    var interactivePins: Bool = true
    /// Tour map: user tapped a star; always the same path (sheet list), whether one stop or many.
    var onClusterTap: ((FloorPinCluster) -> Void)? = nil

    var body: some View {
        Group {
            if let url = URL(string: plan.imageUrl) {
                AsyncImage(url: url) { phase in
                    switch phase {
                    case .success(let image):
                        image
                            .resizable()
                            .scaledToFit()
                            .overlay { pinLayer(clusters: clusters) }
                    case .failure:
                        missingImage
                    case .empty:
                        ProgressView().frame(maxWidth: .infinity, minHeight: 120)
                    @unknown default:
                        EmptyView()
                    }
                }
                .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
            } else {
                missingImage
            }
        }
    }

    private func pinLayer(clusters: [FloorPinCluster]) -> some View {
        GeometryReader { geo in
            let w = geo.size.width
            let h = geo.size.height
            ForEach(clusters) { cluster in
                pinMarker(cluster: cluster)
                    .allowsHitTesting(interactivePins)
                    .position(x: cluster.nx * w, y: cluster.ny * h)
            }
        }
    }

    @ViewBuilder
    private func pinMarker(cluster: FloorPinCluster) -> some View {
        let count = cluster.contexts.count
        let content = ZStack(alignment: .topTrailing) {
            Image(systemName: "star.fill")
                .font(.system(size: 18))
                .symbolRenderingMode(.monochrome)
                .foregroundStyle(Color("Gold"))
                .shadow(color: Color.black.opacity(0.3), radius: 1.5, y: 1)
            if count > 1 {
                Text("\(count)")
                    .font(.system(size: 10, weight: .bold))
                    .foregroundStyle(.white)
                    .frame(minWidth: 16, minHeight: 16)
                    .background(Circle().fill(Color("Gold")))
                    .offset(x: 10, y: -10)
            }
        }
        if interactivePins {
            Button {
                onClusterTap?(cluster)
            } label: {
                content
            }
            .buttonStyle(.plain)
            .accessibilityLabel(count == 1 ? "Tour stop on map" : "\(count) tour stops on map")
            .accessibilityHint("Opens a list of works at this location.")
        } else {
            content
        }
    }

    private var missingImage: some View {
        Image(systemName: "photo")
            .font(.largeTitle)
            .foregroundStyle(.secondary)
            .frame(maxWidth: .infinity, minHeight: 120)
    }
}
