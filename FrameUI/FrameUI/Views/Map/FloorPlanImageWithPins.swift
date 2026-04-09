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
    let pins: [FloorMapPin]

    var body: some View {
        Group {
            if let url = URL(string: plan.imageUrl) {
                AsyncImage(url: url) { phase in
                    switch phase {
                    case .success(let image):
                        image
                            .resizable()
                            .scaledToFit()
                            .overlay { pinLayer(pins: pins) }
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

    private func pinLayer(pins: [FloorMapPin]) -> some View {
        GeometryReader { geo in
            let w = geo.size.width
            let h = geo.size.height
            ForEach(pins) { pin in
                Image(systemName: "star.fill")
                    .font(.system(size: 18))
                    .symbolRenderingMode(.monochrome)
                    .foregroundStyle(Color("Gold"))
                    .shadow(color: Color.black.opacity(0.3), radius: 1.5, y: 1)
                    .position(x: pin.nx * w, y: pin.ny * h)
            }
        }
    }

    private var missingImage: some View {
        Image(systemName: "photo")
            .font(.largeTitle)
            .foregroundStyle(.secondary)
            .frame(maxWidth: .infinity, minHeight: 120)
    }
}
