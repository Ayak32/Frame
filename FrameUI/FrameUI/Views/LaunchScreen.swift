//
//  LaunchScreen.swift
//  FrameUI
//
//  Created by Aya Kasim on 4/7/26.
//

import SwiftUI
import UIKit

private enum SplashOverlay {
    static let windowTag = 1009
}

struct LaunchScreen<RootView: View, Logo: View>: Scene {
    var config: LaunchScreenConfig
    var logo: () -> Logo
    /// Built immediately so the main SwiftUI hierarchy loads under the overlay window.
    var rootContent: RootView

    init(
        config: LaunchScreenConfig = .init(),
        @ViewBuilder logo: @escaping () -> Logo,
        @ViewBuilder rootContent: () -> RootView
    ) {
        self.config = config
        self.logo = logo
        self.rootContent = rootContent()
    }

    var body: some Scene {
        WindowGroup {
            // Matches `UILaunchScreen` / `LaunchScreenBackground` so the first SwiftUI frame isn’t UIKit’s default black
            // while the overlay window is created (async gap after the system launch screen).
            ZStack {
                Color("LaunchScreenBackground")
                    .ignoresSafeArea()
                rootContent
            }
            .modifier(SplashOverlayModifier(config: config, logo: logo))
        }
    }
}

/// Second `UIWindow` above the SwiftUI scene window so the splash covers the full app chrome.
fileprivate struct SplashOverlayModifier<Logo: View>: ViewModifier {
    var config: LaunchScreenConfig
    var logo: () -> Logo

    @State private var splashWindow: UIWindow?

    func body(content: Content) -> some View {
        content
            .onAppear {
                // First attach runs synchronously on the main thread so the overlay appears in the same turn as
                // `onAppear` when possible—reduces a black/clear flash before the splash window exists.
                attachSplashSynchronouslyFirst()
                Task { @MainActor in
                    await attachSplashIfNeeded(retries: 12)
                }
            }
    }

    @MainActor
    private func attachSplashSynchronouslyFirst() {
        guard splashWindow == nil else { return }
        if let window = makeSplashWindow() {
            splashWindow = window
            window.makeKeyAndVisible()
        }
    }

    /// Retries cover the common case where `connectedScenes` is not yet `foregroundActive` on the first `onAppear`.
    @MainActor
    private func attachSplashIfNeeded(retries: Int) async {
        if let existing = splashWindow {
            if !existing.isHidden { existing.makeKeyAndVisible() }
            return
        }

        for _ in 0..<retries {
            if let window = makeSplashWindow() {
                splashWindow = window
                window.makeKeyAndVisible()
                return
            }
            try? await Task.sleep(for: .milliseconds(50))
        }
    }

    @MainActor
    private func makeSplashWindow() -> UIWindow? {
        if let existing = splashWindow {
            return existing.isHidden ? nil : existing
        }

        for scene in UIApplication.shared.connectedScenes {
            guard let windowScene = scene as? UIWindowScene else { continue }
            let state = windowScene.activationState
            guard state == .foregroundActive || state == .foregroundInactive else { continue }
            guard !windowScene.windows.contains(where: { $0.tag == SplashOverlay.windowTag }) else { continue }

            let window = UIWindow(windowScene: windowScene)
            window.tag = SplashOverlay.windowTag
            window.windowLevel = .normal + 1
            window.backgroundColor = .clear

            let host = UIHostingController(
                rootView: LaunchScreenView(
                    config: config,
                    logo: AnyView(logo()),
                    isCompleted: {
                        window.isHidden = true
                        window.isUserInteractionEnabled = false
                        window.rootViewController = nil
                    }
                )
            )
            host.view.backgroundColor = .clear
            window.rootViewController = host
            return window
        }
        return nil
    }
}

struct LaunchScreenConfig {
    /// Match `Assets.xcassets/LaunchScreenBackground` and Info.plist `UILaunchScreen` so the handoff from the system launch screen is seamless.
    var initialDelay: Double = 0.12
    var backgroundColor: Color = Color("LaunchScreenBackground")
    /// Must match the framed size of the logo in `FrameUIApp` (used to compute exit “burst” scale).
    var logoLayoutPoints: CGFloat = 280
    var scaling: CGFloat = 4
    var forceHideLogo: Bool = false
    var animation: Animation = .smooth(duration: 1, extraBounce: 0)
}

fileprivate struct LaunchScreenView: View {
    var config: LaunchScreenConfig
    /// Type-erased so this view does not need a second `Logo` generic (avoids inference failures at the call site).
    var logo: AnyView
    var isCompleted: () -> Void
    @State private var scaleDown = false
    @State private var scaleUp = false

    var body: some View {
        GeometryReader { proxy in
            let w = proxy.size.width
            let h = proxy.size.height
            // Logo is laid out at ~`logoLayoutPoints`; scale up so it can cover the screen when exiting.
            let logoLayoutPoints = Swift.max(config.logoLayoutPoints, 1)
            let coverScale = Swift.max(w, h) / logoLayoutPoints * 1.35 * (config.scaling / 4)

            ZStack {
                Rectangle()
                    .fill(config.backgroundColor)

                logo
                    .scaleEffect(logoScaleMultiplier(coverScale: coverScale))
                    .opacity(scaleUp ? 0 : 1)
            }
            .frame(width: w, height: h)
        }
        .ignoresSafeArea()
        .task {
            guard !scaleDown else { return }
            try? await Task.sleep(for: .seconds(config.initialDelay))
            scaleDown = true
            try? await Task.sleep(for: .seconds(0.1))
            withAnimation(config.animation, completionCriteria: .logicallyComplete) {
                scaleUp = true
            } completion: {
                isCompleted()
            }
        }
    }

    private func logoScaleMultiplier(coverScale: CGFloat) -> CGFloat {
        var s: CGFloat = 1
        if scaleDown { s *= 0.88 }
        if scaleUp { s *= coverScale }
        return s
    }
}
