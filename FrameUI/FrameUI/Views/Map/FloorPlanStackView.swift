//
//  FloorPlanStackView.swift
//  FrameUI
//

import SwiftUI

struct FloorPlanStackView: View {
    /// Tour /tour `retrieved_objects` used to plot `gallery_coordinates` pins.
    var tourObjects: [RetrievedObjectContext] = []

    @State private var plans: [FloorPlan] = []
    @State private var isLoading = true
    @State private var loadFailed = false

    var body: some View {
        Group {
            if isLoading {
                ProgressView()
            } else if loadFailed {
                ContentUnavailableView(
                    "Couldn’t load floor plans",
                    systemImage: "map",
                    description: Text("Check your connection and try opening the map again.")
                )
            } else if plans.isEmpty {
                ContentUnavailableView("No floor plans", systemImage: "map")
            } else {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 0) {
                        ForEach(plans.reversed(), id: \.ref) { plan in
                            VStack(alignment: .leading, spacing: 0) {
                                floorPlanImage(plan: plan, pins: pins(for: plan))
                            }
                        }
                    }
                    .padding()
                }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .navigationTitle("Floor plan")
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
    }

    @ViewBuilder
    private func floorPlanImage(plan: FloorPlan, pins: [TourPin]) -> some View {
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

    private func pinLayer(pins: [TourPin]) -> some View {
        GeometryReader { geo in
            let w = geo.size.width
            let h = geo.size.height
            ForEach(pins) { pin in
                Image(systemName: "paintbrush.pointed.fill")
                    .font(.title2)
                    .symbolRenderingMode(.palette)
                    .foregroundStyle(.white, .red)
                    .shadow(color: .black.opacity(0.35), radius: 2, y: 1)
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

    private func pins(for plan: FloorPlan) -> [TourPin] {
        tourObjects.compactMap { ctx -> TourPin? in
            guard let oid = ctx.object.id?.trimmingCharacters(in: .whitespacesAndNewlines), !oid.isEmpty else {
                return nil
            }
            guard let coords = ctx.galleryCoordinates else { return nil }

            let floorObj = ctx.object.floorNumber
            let floorCoord = coords.floorNumber
            let floor = floorObj ?? floorCoord
            guard let floor, floor == plan.floorNumber else { return nil }

            if let r = coords.ref?.trimmingCharacters(in: .whitespacesAndNewlines), !r.isEmpty, r != plan.ref {
                return nil
            }

            guard let (nx, ny) = normalizedXY(coords: coords, plan: plan) else { return nil }
            return TourPin(id: oid, nx: nx, ny: ny)
        }
    }

    /// Normalized 0…1 in image space (top-left origin), matching Figma-style `nx`/`ny` imports.
    private func normalizedXY(coords: GalleryCoordinates, plan: FloorPlan) -> (CGFloat, CGFloat)? {
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

    private func load() async {
        isLoading = true
        loadFailed = false
        defer { isLoading = false }
        do {
            let res = try await fetchFloorPlans()
            plans = res.floorPlans.sorted {
                $0.floorNumber != $1.floorNumber
                    ? $0.floorNumber < $1.floorNumber
                    : $0.ref < $1.ref
            }
        } catch {
            plans = []
            loadFailed = true
        }
    }
}

private struct TourPin: Identifiable {
    let id: String
    let nx: CGFloat
    let ny: CGFloat
}

#Preview {
    NavigationStack {
        FloorPlanStackView(tourObjects: [])
    }
}
