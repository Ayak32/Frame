//
//  TourRequestView.swift
//  FrameUI
//
//  Created by Aya Kasim on 4/2/26.
//

import SwiftUI

struct TourRequestView: View {
    private static let tourLengthOptions = [30, 60, 90, 120]

    @EnvironmentObject private var session: TourSession

    @State private var query: String = ""
    @State private var timeLimitMinutes: Int = 30
    @State private var floorText: String = ""
    @State private var galleryText: String = ""
    @State private var goToStops = false

    var body: some View {
        ZStack {
            Color("LaunchScreenBackground")
                .ignoresSafeArea()
            Form {
                Section {
                    TextField("A tour about....", text: $query, axis: .vertical)
                        .lineLimit(3...8)

                    Picker("Time available", selection: $timeLimitMinutes) {
                        ForEach(Self.tourLengthOptions, id: \.self) { minutes in
                            Text("\(minutes) min").tag(minutes)
                        }
                    }
                    .pickerStyle(.segmented)
                } header: {
                    Text("What would you like to see?")
                        .font(Font.custom("American Typewriter", size: 14))
                } footer: {
                    Text("Choose how long you’d like to walk. The app picks more stops for longer tours.")
                        .font(.footnote)
                }

                Section("Location filters (optional)") {
                    TextField("Floor number", text: $floorText)
                        .keyboardType(.numberPad)
                    TextField("Gallery number", text: $galleryText)
                        .textInputAutocapitalization(.never)
                }

                if let message = session.errorMessage {
                    Section {
                        Text(message)
                            .foregroundStyle(.red)
                            .font(.subheadline)
                    }
                }

                Section {
                    Button {
                        Task {
                            let floor = parsedFloor(from: floorText)
                            await session.loadTour(
                                query: query,
                                timeLimitMinutes: timeLimitMinutes,
                                floorNumber: floor,
                                galleryNumber: galleryText
                            )
                            if session.errorMessage == nil, session.lastResponse != nil {
                                goToStops = true
                            }
                        }
                    } label: {
                        Text("Start tour")
                            .frame(maxWidth: .infinity)
                    }
                    .disabled(session.isLoading)
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Welcome to  Frame")
        .navigationBarTitleDisplayMode(.large)
        .toolbarBackground(Color("LaunchScreenBackground"), for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
        .navigationDestination(isPresented: $goToStops) {
            TourStopsView()
                .environmentObject(session)
        }
        .fullScreenCover(isPresented: Binding(
            get: { session.isLoading },
            set: { session.isLoading = $0 }
        )) {
            TourLoadingView()
        }
    }

    private func parsedFloor(from text: String) -> Int? {
        let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if t.isEmpty { return nil }
        return Int(t)
    }

}

#if DEBUG
struct BackendTestView: View {
    @State private var result: String = "Tap to test"
    @State private var isLoading = false

    var body: some View {
        VStack(spacing: 12) {
            Text(result)
                .font(.footnote)
                .multilineTextAlignment(.center)

            Button(isLoading ? "Testing..." : "Test Backend") {
                Task {
                    isLoading = true
                    defer { isLoading = false }
                    do {
                        let request = ObjectDescriptionRequest(
                            objectId: "https://media.art.yale.edu/content/lux/obj/69.json",
                            query: "a tour about american revolution",
                            themes: "art in war"
                        )
                        let response: ObjectDescriptionResponse = try await fetchObjectDescription(request: request)
                        result = "Success: \(response)"
                    } catch {
                        result = "Error: \(error.localizedDescription)"
                    }
                }
            }
            .disabled(isLoading)
        }
        .padding()
    }
}
#endif

#Preview("Tour request") {
    NavigationStack {
        TourRequestView()
            .environmentObject(TourSession())
    }
}
