//
//  RootView.swift
//  FrameUI
//
//  Created by Aya Kasim on 3/31/26.
//

import SwiftUI

/// Main app shell shown after the launch overlay dismisses.
struct RootView: View {
    @EnvironmentObject private var tourSession: TourSession

    var body: some View {
        NavigationStack {
            TourRequestView()
        }
    }
}

#Preview {
    RootView()
        .environmentObject(TourSession())
}
