//
//  TourLoadingView.swift
//  FrameUI
//
//  Created by Aya Kasim on 4/6/26.
//

import SwiftUI

struct TourLoadingView: View {
    @EnvironmentObject private var session: TourSession

    var body: some View {
        ZStack {
            Color(.systemGroupedBackground)
                .ignoresSafeArea()

            VStack(spacing: 24) {
                ProgressView()
                    .scaleEffect(1.35)
                    .tint(.primary)

                VStack(spacing: 8) {
                    Text("Building your tour")
                        .font(Font.custom("American Typewriter", size: 22))
                        .multilineTextAlignment(.center)

                    Text("Finding objects that match what you asked for.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 32)
                }
            }
        }
        .interactiveDismissDisabled(true)
    }
}

#Preview {
    TourLoadingView()
        .environmentObject(TourSession())
}
