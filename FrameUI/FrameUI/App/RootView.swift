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

    /// Same as `#FDF6EE` — defined in `Assets.xcassets/LaunchScreenBackground`.
    private var appBackground: Color { Color("LaunchScreenBackground") }

    var body: some View {
        ZStack {
            appBackground.ignoresSafeArea()
            NavigationStack {
                TourRequestView()
            }
        }
    }
}

#Preview {
    RootView()
        .environmentObject(TourSession())
}
