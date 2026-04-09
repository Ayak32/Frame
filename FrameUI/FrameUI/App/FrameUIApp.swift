//
//  FrameUIApp.swift
//  FrameUI
//
//  Created by Aya Kasim on 3/25/26.
//

import SwiftUI
import UIKit

@main
struct FrameUIApp: App {
    /// Matches `Launch Screen.storyboard` constraints (width 280, height 275).
    private static let logoSize = CGSize(width: 280, height: 275)

    @StateObject private var tourSession = TourSession()

    init() {
        // Default UIKit window is black; set it to match `UILaunchScreen` / `LaunchScreenBackground` until SwiftUI paints.
        let cream = UIColor(named: "LaunchScreenBackground")
            ?? UIColor(red: 253 / 255, green: 246 / 255, blue: 238 / 255, alpha: 1)
        UIWindow.appearance().backgroundColor = cream
        // Form/List use UITableView; a solid cream here often still leaves gray margins on iOS 18.
        // Clear lets SwiftUI `.background` / parent `ZStack` colors show through.
        UITableView.appearance().backgroundColor = .clear
        UICollectionView.appearance().backgroundColor = .clear
    }

    var body: some Scene {
        LaunchScreen(config: .init(logoLayoutPoints: Self.logoSize.width, scaling: 9)) {
            // Same asset as Info.plist `UILaunchScreen` → `UIImageName` (`LaunchScreenLogo`).
            // `logoLayoutPoints` must match this frame so the exit animation scales correctly.
            Image("LaunchScreenLogo")
                .renderingMode(.original)
                .resizable()
                .scaledToFit()
                .frame(width: Self.logoSize.width, height: Self.logoSize.height)
        } rootContent: {
            RootView()
                .environmentObject(tourSession)
        }
    }
}

