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

    private var trimmedQuery: String {
        query.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private var canStart: Bool {
        !session.isLoading && !trimmedQuery.isEmpty
    }

    var body: some View {
        ZStack {
            Color("LaunchScreenBackground")
                .ignoresSafeArea()
            Form {
                Section {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Plan a tour")
                            .font(.custom("American Typewriter", size: 24))
                        Text("Tell Frame what you’re curious about. We’ll build a route for the time you have.")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 6)
                }
                .listRowBackground(Color("LaunchScreenBackground"))

                Section {
                    TextField("What would you like to see?", text: $query, axis: .vertical)
                        .lineLimit(3...8)
                        .textInputAutocapitalization(.sentences)
                        .submitLabel(.done)

                    Picker("Time available", selection: $timeLimitMinutes) {
                        ForEach(Self.tourLengthOptions, id: \.self) { minutes in
                            Text("\(minutes) min").tag(minutes)
                        }
                    }
                    .pickerStyle(.segmented)
                } footer: {
                    Text("Longer tours include more stops.")
                        .font(.footnote)
                }
                .listRowBackground(Color("LaunchScreenBackground"))

//                Section("Location filters (optional)") {
//                    TextField("Floor", text: $floorText)
//                        .keyboardType(.numberPad)
//                    TextField("Gallery", text: $galleryText)
//                        .textInputAutocapitalization(.never)
//                }
                .listRowBackground(Color("LaunchScreenBackground"))

                if let message = session.errorMessage {
                    Section {
                        Text(message)
                            .foregroundStyle(.red)
                            .font(.subheadline)
                    }
                    .listRowBackground(Color("LaunchScreenBackground"))
                }

                Section {
                    HStack {
                        Spacer(minLength: 0)
                        Button {
                            guard canStart else { return }
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
                            HStack(spacing: 10) {
                                if session.isLoading {
                                    ProgressView()
                                        .tint(.primary)
                                }
                                Text(session.isLoading ? "Building tour…" : "Start tour")
                                    .font(.headline)
                            }
                            .padding(.horizontal, 22)
                            .frame(height: 30)
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(Color(red: 0.18, green: 0.14, blue: 0.12))
                        .foregroundStyle(Color("LaunchScreenBackground"))
                        // only block taps
                        .allowsHitTesting(canStart)
                        Spacer(minLength: 0)
                    }
                }
                .listRowBackground(Color("LaunchScreenBackground"))
            }
            .scrollContentBackground(.hidden)
        }
        .safeAreaInset(edge: .top) {
            // Pinned header at the very top of the view.
            VStack(spacing: 10) {
                Text("Welcome to Frame")
                    .font(.custom("American Typewriter", size: 33))
                    .frame(maxWidth: .infinity, alignment: .center)

                Rectangle()
                    .fill(Color.primary.opacity(0.18))
                    .frame(width: 140, height: 1)
            }
            .padding(.horizontal, 20)
            .padding(.top, 2)
            .padding(.bottom, 18)
            .background(Color("LaunchScreenBackground"))
        }
        .navigationTitle("")
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
